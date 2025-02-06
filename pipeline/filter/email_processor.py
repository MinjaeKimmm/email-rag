from typing import Dict, List, Optional
from langchain_core.runnables import RunnableBranch, RunnableLambda, RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

from pipeline.common.base_agent import BaseAgent
from pipeline.preprocess.email_classifier_v3 import EmailClassifier

class EmailPreprocessor(BaseAgent):
    """Agent for preprocessing emails (cleaning, normalizing, etc)."""
    
    def get_system_message(self) -> str:
        return """You are an expert email preprocessor. Clean and normalize email content."""
    
    def get_prompt(self, conversation: Dict) -> str:
        message = conversation['Messages'][0]
        return f"""Clean and normalize this email content:
        {message['Body']}
        
        Return a JSON with:
        {{"cleaned_content": "cleaned email body"}}
        """
    
    def validate_output(self, output: str) -> Optional[Dict]:
        try:
            parsed = json.loads(output)
            if "cleaned_content" not in parsed:
                return None
            return parsed
        except:
            return None

class EmailSummarizer(BaseAgent):
    """Agent for creating concise email summaries."""
    
    def get_system_message(self) -> str:
        return """You are an expert email summarizer. Create concise, informative summaries."""
    
    def get_prompt(self, email_data: Dict) -> str:
        return f"""Create a brief summary of this email:
        {email_data.get('cleaned_content', email_data['Messages'][0]['Body'])}
        
        Return a JSON with:
        {{"summary": "brief summary"}}
        """
    
    def validate_output(self, output: str) -> Optional[Dict]:
        try:
            parsed = json.loads(output)
            if "summary" not in parsed:
                return None
            return parsed
        except:
            return None

def check_attachments(conversation: Dict) -> bool:
    """Check if email has attachments."""
    return bool(conversation['Messages'][0].get('AttachmentFiles'))

def create_email_processing_chain():
    """Create a complex email processing chain with branches."""
    
    preprocessor = EmailPreprocessor()
    classifier = EmailClassifier()
    summarizer = EmailSummarizer()
    
    # Chain for emails with attachments
    attachment_chain = (
        RunnablePassthrough()
        | preprocessor
        | summarizer
        | RunnableLambda(lambda x: {**x, "has_attachments": True})
    )
    
    # Chain for emails without attachments
    no_attachment_chain = (
        preprocessor
        | classifier
        | summarizer
        | RunnableLambda(lambda x: {**x, "has_attachments": False})
    )
    
    # Branch based on whether email has attachments
    return RunnableBranch(
        (
            RunnableLambda(check_attachments),
            attachment_chain
        ),
        no_attachment_chain
    )

def process_email(conversation: Dict) -> Dict:
    """Process a single email conversation through the chain."""
    chain = create_email_processing_chain()
    return chain.invoke(conversation)

if __name__ == "__main__":
    import json
    from pathlib import Path
    
    # Example usage
    root_dir = Path(__file__).parent.parent.parent
    input_path = root_dir / 'data' / 'single_message_conversations.json'
    
    with open(input_path, 'r') as f:
        conversations = json.load(f)
    
    # Process first email as example
    result = process_email(conversations[0])
    print("\nProcessing Result:")
    print(json.dumps(result, indent=2))
