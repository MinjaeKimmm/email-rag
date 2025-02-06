"""Module for generating QA pairs from investment-related emails."""

import json
import warnings
from pathlib import Path
from typing import Dict, List, Optional
from tqdm import tqdm
from langchain_core.runnables import chain

from pipeline.common.base_agent import BaseAgent
from pipeline.common.prompt import EMAIL_QA_PROMPT_TEMPLATE
from pipeline.common.example_messages import get_email_qa_messages

class QAGenerator(BaseAgent):
    """Agent for generating Q&A pairs from investment-related emails."""
    
    def get_example_messages(self) -> List[Dict[str, str]]:
        return get_email_qa_messages()
    
    def get_prompt(self, conversation: Dict) -> str:
        """Create a prompt for generating QA pairs from a single email conversation."""
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
                    content_preview = attachment['content'][:3000]
                    if len(attachment['content']) > 3000:
                        content_preview += "..."
                    attachment_content += f"Content preview:\n{content_preview}\n"
                attachment_content += "\n"
        else:
            attachment_content = "No attachments in this email."
        
        return EMAIL_QA_PROMPT_TEMPLATE.format(
            subject=message['Subject'],
            sender_name=message['SenderName'],
            sender_email=message['SenderEmail'],
            to=message['To'],
            received_time=message['ReceivedTime'],
            conversation_topic=message['ConversationTopic'],
            body=message['Body'],
            attachment_content=attachment_content
        )
    
    def validate_output(self, output: str) -> Optional[Dict]:
        """Validate the QA generation output from the LLM."""
        try:
            parsed = json.loads(output)
            
            # Validate required fields
            required_fields = ["thought_process", "question", "answer"]
            if not all(k in parsed for k in required_fields):
                print("Error: Missing required fields in model output")
                return None
            
            # Validate thought process
            if not isinstance(parsed["thought_process"], list) or len(parsed["thought_process"]) < 2:
                print("Error: Invalid thought process format")
                return None
            
            # Validate question and answer are non-empty
            if not all(parsed[k].strip() for k in ["question", "answer"]):
                print("Error: Empty question or answer")
                return None
            
            return parsed
            
        except json.JSONDecodeError:
            print("Error: Invalid JSON format in response")
            return None

def run_qa_generation(input_file: str = "included_emails.json", output_file: str = "qa_pairs.json", save_every: int = 10):
    """
    Generate QA pairs from processed emails with incremental saving.
    
    Args:
        input_file: Name of the input JSON file in the data/processed_emails directory
        output_file: Name of the output JSON file to store QA pairs in the data directory
        save_every: Save progress after processing this many conversations
    """
    # Suppress warnings
    warnings.filterwarnings('ignore', category=UserWarning)
    
    data_dir = Path(__file__).parent.parent.parent / 'data'
    input_path = data_dir / 'processed_emails' / input_file
    output_path = data_dir / output_file
    temp_path = data_dir / f"{output_file}.temp"
    
    print("\n=== Starting QA Generation Pipeline ===")
    
    # Load conversations
    print(f"\nLoading conversations from {input_path}")
    with open(input_path, 'r', encoding='utf-8') as f:
        conversations = json.load(f)
    print(f"Found {len(conversations)} conversations")
    
    # Check for existing progress
    qa_pairs = []
    processed_ids = set()
    if temp_path.exists():
        print("\nFound existing progress, loading...")
        with open(temp_path, 'r', encoding='utf-8') as f:
            qa_pairs = json.load(f)
        processed_ids = {pair['Conversation_ID'] for pair in qa_pairs}
        print(f"Loaded {len(qa_pairs)} existing QA pairs")
    
    # Filter out already processed conversations
    remaining_conversations = [
        conv for conv in conversations 
        if conv['conversation']['ConversationID'] not in processed_ids
    ]
    print(f"Remaining conversations to process: {len(remaining_conversations)}")
    
    # Generate QA pairs
    print("\nStep 1: Generating QA pairs...")
    generator = QAGenerator()
    error_count = 0
    
    def save_progress():
        """Save current progress to temp file"""
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(qa_pairs, f, ensure_ascii=False, indent=2)
        print(f"\nProgress saved: {len(qa_pairs)} QA pairs")
    
    try:
        pbar = tqdm(total=len(remaining_conversations), ascii=True)
        for i, conv in enumerate(remaining_conversations, 1):
            try:
                result = generator.invoke(conv['conversation'])
                if result:
                    qa_pairs.append({
                        "Question": result["question"],
                        "Conversation_ID": conv['conversation']["ConversationID"],
                        "Answer": result["answer"],
                        "Thought_Process": result["thought_process"]
                    })
            except Exception as e:
                error_count += 1
                print(f"\nError processing conversation {conv['conversation']['ConversationID']}: {str(e)}")
            
            # Save progress periodically
            if i % save_every == 0:
                save_progress()
            
            pbar.update(1)
        pbar.close()
        
        # Final save of progress
        save_progress()
        
        # Move temp file to final output
        temp_path.rename(output_path)
        
    except KeyboardInterrupt:
        print("\n\nInterrupted! Saving current progress...")
        save_progress()
        print("You can resume later by running the script again")
        return qa_pairs
    
    print("\n=== QA Generation Pipeline Complete! ===")
    print(f"Total conversations processed: {len(conversations)}")
    print(f"Successfully generated QA pairs: {len(qa_pairs)}")
    print(f"Errors encountered: {error_count}")
    print(f"Results saved to: {output_path}")
    
    return qa_pairs
