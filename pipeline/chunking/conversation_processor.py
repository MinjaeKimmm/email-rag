from typing import List, Dict, Any, Generator
from pathlib import Path
from .document_chunker import DocumentChunker
from .base import Chunk
from pipeline.preprocess.attachment_processor import DocumentProcessor

class ConversationProcessor:
    """Process entire email conversations including all messages and attachments"""
    
    def __init__(self, dataset: str, base_dir: str = None):
        self.document_chunker = DocumentChunker(dataset)
        self.attachment_processor = DocumentProcessor(base_dir)
        
    def process_conversation(self, conversation: Dict[str, Any]) -> Generator[Chunk, None, None]:
        """Process an entire conversation including all messages and attachments
        
        Args:
            conversation: Dictionary containing conversation data with messages and attachments
            
        Yields:
            Chunk objects for email bodies and attachments
        """
        conversation_id = conversation['ConversationID']
        
        # Process each message in the conversation
        for message in conversation['Messages']:
            # Process email body
            yield from self._process_message_body(conversation, message)
            
            # Process attachments if any
            # Only use pre-processed Attachments from included_emails.json
            if 'Attachments' in message and message['Attachments']:
                yield from self._process_message_attachments_with_content(conversation_id, message)

    def _process_message_body(self, conversation: Dict[str, Any], message: Dict[str, Any]) -> Generator[Chunk, None, None]:
        """Process a single message body"""
        # Create metadata for the message
        metadata = {
            'ConversationID': conversation['ConversationID'],
            'Topic': conversation.get('Topic', ''),
            'Messages': [message]  # Include only the current message
        }
        
        # Process the message body
        chunks = self.document_chunker.process_document(
            content=message['Body'],
            metadata=metadata
        )
        yield from chunks

    def _process_message_attachments_with_content(self, conversation_id: str, message: Dict[str, Any]) -> Generator[Chunk, None, None]:
        """Process attachments that already have content"""
        for attachment in message['Attachments']:
            try:
                if 'error' in attachment or not attachment.get('content'):
                    print(f"Skipping attachment due to error or missing content: {attachment.get('error', 'No content')}")
                    continue
                    
                # Get file extension (without leading dot)
                extension = attachment.get('type', '').lower() if attachment.get('type') else ''
                
                # Parse received time into year, month, day
                received_time = message['ReceivedTime']
                year = int(received_time[:4])
                month = int(received_time[5:7])
                day = int(received_time[8:10])
                
                # Create metadata using parent email info
                metadata = {
                    'conversation_id': conversation_id,
                    'subject': message['Subject'],
                    'sender_name': message['SenderName'],
                    'sender_email': message['SenderEmail'],
                    'year': year,
                    'month': month,
                    'day': day,
                    'extension': '.' + extension.lstrip('.') if extension else '',  # Add dot prefix here and remove any existing dots
                    'attachment_metadata': {
                        'extension': extension.lstrip('.'),  # Store without dot in metadata
                        'file_name': attachment.get('path', '').split('/')[-1] if attachment.get('path') else '',
                        'document_type': extension.lstrip('.').upper() + ' Document' if extension else 'Unknown Document'
                    }
                }
                
                # Process the content
                chunks = self.document_chunker.process_document(
                    content=attachment['content'],
                    metadata=metadata
                )
                yield from chunks
                    
            except Exception as e:
                print(f"Error processing attachment: {str(e)}")
                continue

def process_conversations(conversations_file: str, dataset: str, base_dir: str = None) -> Generator[Chunk, None, None]:
    """Process all conversations from a JSON file
    
    Args:
        conversations_file: Path to JSON file containing conversations
        dataset: Name of the dataset
        base_dir: Base directory for relative attachment paths
        
    Yields:
        Chunk objects for all email bodies and attachments
    """
    import json
    
    processor = ConversationProcessor(dataset, base_dir)
    
    with open(conversations_file, 'r') as f:
        conversations = json.load(f)
        
    for conversation in conversations:
        yield from processor.process_conversation(conversation)
