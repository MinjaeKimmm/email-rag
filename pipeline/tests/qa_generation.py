import json
from pathlib import Path
from typing import Dict, List
import typer

from pipeline.eval.generate_qa_data import QAGenerator
from pipeline.common.prompt import EMAIL_QA_PROMPT_TEMPLATE
from pipeline.common.example_messages import get_email_qa_messages

app = typer.Typer()

CONVERSATIONS_PATH = Path(__file__).parent.parent.parent / 'data' / 'processed_emails' / 'included_emails.json'

def load_test_conversations() -> List[Dict]:
    """Load test conversations from the data directory."""
    with open(CONVERSATIONS_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
        # Convert to list if it's a dict
        if isinstance(data, dict):
            data = [data]
        # Extract conversation data from the nested structure
        return [item['conversation'] for item in data]

def get_prompt_for_email(index: int = 0) -> str:
    """Get the prompt for a specific email."""
    conversations = load_test_conversations()
    
    if index >= len(conversations):
        raise ValueError(f"Index {index} is out of range. Only {len(conversations)} conversations available.")
    
    conversation = conversations[index]
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

def test_qa_generation(index: int = 0) -> Dict:
    """Test the QA generator with a specific email."""
    generator = QAGenerator()
    conversations = load_test_conversations()
    
    if index >= len(conversations):
        raise ValueError(f"Index {index} is out of range. Only {len(conversations)} conversations available.")
    
    result = generator.invoke(conversations[index])
    if result:
        # Transform into final format
        return {
            "Question": result["question"],
            "Conversation_ID": conversations[index]["ConversationID"],
            "Answer": result["answer"]
        }
    return None

def find_emails_with_attachments():
    """Find and print emails that have attachments."""
    conversations = load_test_conversations()
    
    print("\nEmails with attachments:")
    print("-" * 80)
    for idx, conv in enumerate(conversations):
        message = conv['Messages'][0]
        if 'Attachments' in message and message['Attachments']:
            print(f"\nIndex {idx}:")
            print(f"ConversationID: {conv['ConversationID']}")
            print(f"Subject: {message['Subject']}")
            print(f"From: {message['SenderName']} ({message['SenderEmail']})")
            print("Attachments:")
            for att in message['Attachments']:
                print(f"- {att['type']}: {att.get('path', 'No path')}")

def test_batch_qa_generation(start_index: int = 0, count: int = 5):
    """Test QA generation on a batch of emails."""
    conversations = load_test_conversations()
    generator = QAGenerator()
    qa_pairs = []
    
    end_index = min(start_index + count, len(conversations))
    
    print(f"\nGenerating QA pairs for emails {start_index} to {end_index-1}")
    print("-" * 80)
    
    for idx in range(start_index, end_index):
        print(f"\nProcessing email {idx}...")
        result = generator.invoke(conversations[idx])
        if result:
            # Print summary
            print(f"Generated question:")
            print(f"{result['question']}")
            
            # Add to QA pairs
            qa_pairs.append({
                "Question": result["question"],
                "Conversation_ID": conversations[idx]["ConversationID"],
                "Answer": result["answer"]
            })
    
    return qa_pairs

@app.command()
def main(
    index: int = typer.Argument(0, help="Index of the email to process"),
    prompt: bool = typer.Option(False, "--prompt", help="Show the prompt that would be used"),
    generate: bool = typer.Option(False, "--generate", help="Generate QA pairs"),
    batch: bool = typer.Option(False, "--batch", help="Run batch QA generation"),
    count: int = typer.Option(5, "--count", help="Number of emails to process in batch mode"),
    list_attachments: bool = typer.Option(False, "--list-attachments", help="List all emails with attachments")
):
    """Test the QA generation system."""
    if list_attachments:
        find_emails_with_attachments()
        return

    if prompt:
        print("\nPrompt for email at index", index)
        print("-" * 80)
        print(get_prompt_for_email(index))
    
    if generate and not batch:
        print("\nQA Generation result:")
        print("-" * 80)
        result = test_qa_generation(index)
        if result:
            print(json.dumps(result, indent=2))
        else:
            print("Failed to generate QA pairs")
    
    if batch:
        result = test_batch_qa_generation(index, count)
        if result:
            print("\nGenerated QA pairs:")
            print("-" * 80)
            print(json.dumps(result, indent=2))
        else:
            print("Failed to generate QA pairs")

if __name__ == "__main__":
    app()
