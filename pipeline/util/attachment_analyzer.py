from pathlib import Path
import json
from collections import defaultdict
import warnings
from pipeline.preprocess.attachment_processor import DocumentProcessor

# Suppress openpyxl warnings
warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

def analyze_attachments(input_file: str = "email_conversations.json") -> tuple[list, dict]:
    """
    Analyze attachments in email conversations.
    
    Returns:
        tuple containing:
        - list of dicts with conversation_id, message info, and attachment paths
        - dict of file extensions and their counts
    """
    root_dir = Path(__file__).parent.parent.parent
    input_path = root_dir / 'data' / input_file
    
    # Track attachments and their file types
    attachments_info = []
    extension_counts = defaultdict(int)
    
    with open(input_path, 'r') as f:
        conversations = json.load(f)
    
    for conv in conversations:
        conv_id = conv['ConversationID']
        for msg in conv['Messages']:
            if msg['AttachmentFiles']:  # If not empty list
                for attachment in msg['AttachmentFiles']:
                    # Get file extension
                    ext = Path(attachment).suffix.lower()
                    extension_counts[ext] += 1
                    
                    # Store attachment info
                    attachments_info.append({
                        'conversation_id': conv_id,
                        'message_subject': msg['Subject'],
                        'message_time': msg['ReceivedTime'],
                        'attachment_path': attachment,
                        'file_type': ext
                    })
    
    return attachments_info, dict(extension_counts)

def read_msg_preview(file_path: str, max_lines: int = 10) -> str:
    """Read first few lines of a .msg file"""
    # Convert the Windows-style path to a proper Path object
    path_parts = file_path.replace('\\', '/').split('/')
    full_path = Path(__file__).parent.parent.parent / 'data' / '/'.join(path_parts)
    
    try:
        # .msg files are binary files, not text files
        if full_path.suffix.lower() == '.msg':
            return "(Binary .msg file - cannot display preview. Use an email client to view contents.)"
            
        # For other files, try to read as text
        with open(full_path, 'r', encoding='utf-8') as f:
            lines = []
            for i, line in enumerate(f):
                if i >= max_lines:
                    break
                lines.append(line.strip())
            return '\n'.join(lines)
    except Exception as e:
        return f"Error reading file: {str(e)}"

def process_attachments(input_file: str = "email_conversations.json", output_file: str = "email_conversations_with_attachments.json") -> None:
    """
    Process attachments in email conversations and add processed content to the JSON.
    
    Args:
        input_file: Input JSON file containing email conversations
        output_file: Output JSON file to write processed conversations
    """
    root_dir = Path(__file__).parent.parent.parent
    input_path = root_dir / 'data' / input_file
    output_path = root_dir / 'data' / output_file
    
    print(f"\nProcessing attachments from {input_path}")
    print(f"Output will be written to {output_path}")
    
    # Initialize document processor
    doc_processor = DocumentProcessor()
    
    with open(input_path, 'r') as f:
        conversations = json.load(f)
    
    print(f"\nFound {len(conversations)} conversations to process")
    processed_count = 0
    error_count = 0
    
    # Process each conversation
    for conv_idx, conv in enumerate(conversations, 1):
        print(f"\nProcessing conversation {conv_idx}/{len(conversations)} (ID: {conv['ConversationID']})")
        for msg in conv['Messages']:
            attachments = []
            if msg['AttachmentFiles']:  # If not empty list
                print(f"Found {len(msg['AttachmentFiles'])} attachments in message")
                for attachment in msg['AttachmentFiles']:
                    # Get file extension
                    ext = Path(attachment).suffix.lower()
                    print(f"Processing attachment: {attachment} (type: {ext})")
                    
                    # Only process supported document types
                    if ext in ['.pdf', '.docx', '.xlsx']:
                        try:
                            # Convert Windows path to proper Path object
                            path_parts = attachment.replace('\\', '/').split('/')
                            full_path = root_dir / 'data' / '/'.join(path_parts)
                            print(f"Full path: {full_path}")
                            
                            if not full_path.exists():
                                raise FileNotFoundError(f"File does not exist: {full_path}")
                            
                            # Process the document and get all processed documents
                            print("Processing document...")
                            processed_docs = list(doc_processor.process_document(str(full_path)))
                            print(f"Got {len(processed_docs)} processed documents")
                            
                            # Combine all document contents
                            combined_content = "\n\n".join(doc.content for doc in processed_docs)
                            
                            # Add to attachments list
                            attachments.append({
                                'path': attachment,
                                'type': ext,
                                'content': combined_content,
                                'metadata': [doc.metadata for doc in processed_docs]
                            })
                            processed_count += 1
                            print("Successfully processed attachment")
                        except Exception as e:
                            error_msg = f"Error processing {attachment}: {str(e)}"
                            print(error_msg)
                            # Add error information to attachments
                            attachments.append({
                                'path': attachment,
                                'type': ext,
                                'error': error_msg
                            })
                            error_count += 1
            
            # Add attachments field to message
            msg['Attachments'] = attachments
    
    print(f"\nProcessing complete!")
    print(f"Successfully processed: {processed_count} attachments")
    print(f"Errors encountered: {error_count} attachments")
    
    # Write processed conversations to output file
    print(f"\nWriting results to {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        # Use indent=2 for pretty printing and ensure_ascii=False for proper Unicode handling
        json.dump(conversations, f, indent=2, ensure_ascii=False)
    print("Done!")

if __name__ == "__main__":
    # Analyze attachments
    attachments, extensions = analyze_attachments()
    
    # Print summary of file extensions
    print("\nFile Extensions Found:")
    for ext, count in sorted(extensions.items(), key=lambda x: (-x[1], x[0])):
        print(f"{ext}: {count} files")
    
    process_attachments()
