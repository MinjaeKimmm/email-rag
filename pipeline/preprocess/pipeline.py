"""Pipeline for preprocessing email content and attachments."""

import json
import warnings
from pathlib import Path
from tqdm import tqdm
from .email_preprocessor import EmailPreprocessor
from .attachment_processor import DocumentProcessor

def run_preprocess(input_file: str = "email_conversations.json") -> None:
    """
    Run the preprocessing pipeline that handles both email body and attachments.
    
    Args:
        input_file: Name of the input JSON file in the data directory
    """
    # Suppress warnings
    warnings.filterwarnings('ignore', category=UserWarning)
    warnings.filterwarnings('ignore', module='bs4')
    
    root_dir = Path(__file__).parent.parent.parent
    input_path = root_dir / 'data' / input_file
    output_path = root_dir / 'data' / 'preprocessed_email_conversations.json'
    
    print("\n=== Starting Email Preprocessing Pipeline ===")
    
    # Load conversations
    print(f"\nLoading conversations from {input_path}")
    with open(input_path, 'r', encoding='utf-8') as f:
        conversations = json.load(f)
    print(f"Found {len(conversations)} conversations")
    
    # Step 1: Preprocess email body content
    print("\nStep 1: Processing email body content...")
    preprocessor = EmailPreprocessor()
    
    processed_conversations = []
    pbar = tqdm(total=len(conversations), ascii=True)
    for conv in conversations:
        processed_conv = conv.copy()
        processed_messages = []
        
        for msg in conv['Messages']:
            processed_msg = msg.copy()
            processed_msg['Body'] = preprocessor.preprocess_email_body(msg['Body'])
            processed_messages.append(processed_msg)
            
        processed_conv['Messages'] = processed_messages
        processed_conversations.append(processed_conv)
        pbar.update(1)
    pbar.close()
    
    print("Email body preprocessing complete!")
    
    # Step 2: Process attachments
    print("\nStep 2: Processing attachments...")
    doc_processor = DocumentProcessor()
    
    processed_count = 0
    error_count = 0
    total_attachments = sum(len(msg['AttachmentFiles']) 
                          for conv in processed_conversations 
                          for msg in conv['Messages'])
    
    pbar = tqdm(total=total_attachments, ascii=True)
    for conv in processed_conversations:
        for msg in conv['Messages']:
            attachments = []
            if msg['AttachmentFiles']:
                for attachment in msg['AttachmentFiles']:
                    ext = Path(attachment).suffix.lower()
                    
                    if ext in ['.pdf', '.docx', '.xlsx']:
                        try:
                            path_parts = attachment.replace('\\', '/').split('/')
                            full_path = root_dir / 'data' / '/'.join(path_parts)
                            
                            if not full_path.exists():
                                raise FileNotFoundError(f"File does not exist: {full_path}")
                            
                            processed_docs = list(doc_processor.process_document(str(full_path)))
                            combined_content = "\n\n".join(doc.content for doc in processed_docs)
                            
                            attachments.append({
                                'path': attachment,
                                'type': ext,
                                'content': combined_content,
                                'metadata': [doc.metadata for doc in processed_docs]
                            })
                            processed_count += 1
                        except Exception as e:
                            error_msg = f"Error processing {attachment}: {str(e)}"
                            print(f"\nError: {error_msg}")
                            attachments.append({
                                'path': attachment,
                                'type': ext,
                                'error': error_msg
                            })
                            error_count += 1
                    pbar.update(1)
            
            msg['Attachments'] = attachments
    pbar.close()
    
    print("\nAttachment processing complete!")
    print(f"Successfully processed: {processed_count} attachments")
    print(f"Errors encountered: {error_count} attachments")
    
    # Save final preprocessed result
    print(f"\nWriting preprocessed results to {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(processed_conversations, f, indent=2, ensure_ascii=False)
    
    print("\n=== Preprocessing Pipeline Complete! ===")
    print(f"Output saved to: {output_path}")
