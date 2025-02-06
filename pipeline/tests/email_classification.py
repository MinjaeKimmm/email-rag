import json
from pathlib import Path
from typing import Dict, List
import typer

from pipeline.preprocess.email_classifier import EmailClassifier
from pipeline.common.prompt import EMAIL_CLASSIFICATION_PROMPT_TEMPLATE

app = typer.Typer()

CONVERSATIONS_PATH = Path(__file__).parent.parent.parent / 'data' / 'email_conversations_with_attachments.json'

def load_test_conversations() -> List[Dict]:
    """Load test conversations from the data directory."""
    with open(CONVERSATIONS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

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

def test_classification(index: int = 0) -> Dict:
    """Test the email classifier with a specific email."""
    classifier = EmailClassifier()
    conversations = load_test_conversations()
    
    if index >= len(conversations):
        raise ValueError(f"Index {index} is out of range. Only {len(conversations)} conversations available.")
    
    return classifier.invoke(conversations[index])

def find_emails_with_attachments():
    """Find and print emails that have attachments."""
    conversations = load_test_conversations()
    
    print("\nEmails with attachments:")
    print("-" * 80)
    for idx, conv in enumerate(conversations):
        message = conv['Messages'][0]
        if 'Attachments' in message and message['Attachments']:
            print(f"\nIndex {idx}:")
            print(f"Subject: {message['Subject']}")
            print(f"From: {message['SenderName']} ({message['SenderEmail']})")
            print("Attachments:")
            for att in message['Attachments']:
                print(f"- {att['type']}: {att['path']}")

@app.command()
def main(
    index: int = typer.Argument(0, help="Index of the email to process"),
    prompt: bool = typer.Option(False, "--prompt", help="Show the prompt that would be used"),
    classify: bool = typer.Option(False, "--classify", help="Run the classification"),
    list_attachments: bool = typer.Option(False, "--list-attachments", help="List all emails with attachments")
):
    """Test the email classification system."""
    if list_attachments:
        find_emails_with_attachments()
        return

    if prompt:
        print("\nPrompt for email at index", index)
        print("-" * 80)
        print(get_prompt_for_email(index))
    
    if classify:
        print("\nClassification result:")
        print("-" * 80)
        result = test_classification(index)
        print(json.dumps(result, indent=2))

if __name__ == "__main__":
    app()