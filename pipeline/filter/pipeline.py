"""Pipeline for filtering and classifying emails."""

import json
import warnings
from pathlib import Path
from tqdm import tqdm
from .email_filter import split_conversations_by_message_count
from .email_classifier import EmailClassifier

def run_filter(input_file: str, output_dir: str) -> None:
    """
    Run the email filtering and classification pipeline.
    
    Args:
        input_file: Name of the input JSON file in the data directory
        output_dir: Name of the output directory in the data directory
    """
    # Suppress warnings
    warnings.filterwarnings('ignore', category=UserWarning)
    
    root_dir = Path(__file__).parent.parent.parent
    input_path = root_dir / 'data' / input_file
    output_dir_path = root_dir / 'data' / output_dir
    output_dir_path.mkdir(exist_ok=True)
    
    print("\n=== Starting Email Filter Pipeline ===")
    
    # Load preprocessed conversations
    print(f"\nLoading preprocessed conversations from {input_path}")
    with open(input_path, 'r') as f:
        conversations = json.load(f)
    print(f"Found {len(conversations)} conversations")
    
    # Step 1: Split conversations by message count
    print("\nStep 1: Splitting conversations by message count...")
    single_conversations, multi_conversations = split_conversations_by_message_count(conversations)
    print(f"Found {len(single_conversations)} single-message conversations")
    print(f"Found {len(multi_conversations)} multi-message conversations")
    
    # Save multi-message conversations
    multi_msg_path = output_dir_path / 'multi_message_conversations.json'
    print(f"\nSaving multi-message conversations to {multi_msg_path}")
    with open(multi_msg_path, 'w') as f:
        json.dump(multi_conversations, f, indent=2)
    
    # Step 2: Classify single message conversations
    print("\nStep 2: Classifying single message conversations...")
    classifier = EmailClassifier()
    
    included = []
    excluded = []
    pbar = tqdm(total=len(single_conversations), ascii=True)
    
    for conv in single_conversations:
        try:
            result = classifier.invoke(conv)
            if result:
                if result['decision'] == 'INCLUDE':
                    included.append({
                        'conversation_id': conv['ConversationID'],
                        'conversation': conv,
                        'classification': result
                    })
                else:
                    excluded.append({
                        'conversation_id': conv['ConversationID'],
                        'conversation': conv,
                        'classification': result
                    })
        except Exception as e:
            print(f"\nError processing conversation {conv['ConversationID']}: {str(e)}")
        pbar.update(1)
    pbar.close()
    
    # Save results
    print("\nStep 3: Saving classification results...")
    included_path = output_dir_path / 'included_emails.json'
    print(f"Writing {len(included)} included emails to {included_path}")
    with open(included_path, 'w') as f:
        json.dump(included, f, indent=2)
    
    excluded_path = output_dir_path / 'excluded_emails.json'
    print(f"Writing {len(excluded)} excluded emails to {excluded_path}")
    with open(excluded_path, 'w') as f:
        json.dump(excluded, f, indent=2)
    
    print("\n=== Filter Pipeline Complete! ===")
    print(f"Results saved in: {output_dir_path}")
    print(f"Multi-message conversations: {len(multi_conversations)}")
    print(f"Included single-message emails: {len(included)}")
    print(f"Excluded single-message emails: {len(excluded)}")
