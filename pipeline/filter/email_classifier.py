from pathlib import Path
from typing import Dict, List, Optional
import json
from langchain_core.runnables import chain

from pipeline.common.base_agent import BaseAgent
from pipeline.common.prompt import EMAIL_CLASSIFICATION_PROMPT_TEMPLATE
from pipeline.common.example_messages import get_email_classification_messages


class EmailClassifier(BaseAgent):
    """Agent for classifying emails for financial RAG system."""
    
    def get_example_messages(self) -> List[Dict[str, str]]:
        return get_email_classification_messages()
    
    def get_prompt(self, conversation: Dict) -> str:
        """Create a prompt for classifying a single email conversation."""
        message = conversation['Messages'][0]
        
        # Process attachments if present
        attachment_content = ""
        if 'Attachments' in message and message['Attachments']:
            attachment_content = "The email contains the following attachments:\n\n"
            for idx, attachment in enumerate(message['Attachments'], 1):
                attachment_content += f"Attachment {idx} ({attachment['type']}):\n"
                if 'error' in attachment:
                    attachment_content += f"Error processing attachment: {attachment['error']}\n"
                else:
                    # Take first 500 characters of content as preview
                    content_preview = attachment['content'][:500]
                    if len(attachment['content']) > 500:
                        content_preview += "..."
                    attachment_content += f"Content preview:\n{content_preview}\n"
                attachment_content += "\n"
        else:
            attachment_content = "No attachments in this email."
        
        return EMAIL_CLASSIFICATION_PROMPT_TEMPLATE.format(
            topic=conversation['Topic'],
            subject=message['Subject'],
            sender_name=message['SenderName'],
            sender_email=message['SenderEmail'],
            to=message['To'],
            conversation_topic=message['ConversationTopic'],
            body=message['Body'],
            attachment_content=attachment_content
        )
    
    def validate_output(self, output: str) -> Optional[Dict]:
        """Validate the classification output from the LLM."""
        try:
            parsed = json.loads(output)
            
            # Validate required fields
            required_fields = ["thought_process", "decision", "category"]
            if not all(k in parsed for k in required_fields):
                print("Error: Missing required fields in model output")
                return None
            
            # Validate decision value
            if parsed["decision"] not in ["INCLUDE", "EXCLUDE"]:
                print("Error: Invalid decision value")
                return None
            
            return parsed
            
        except json.JSONDecodeError:
            print("Error: Invalid JSON format in response")
            return None
