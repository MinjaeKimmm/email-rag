import json
from pathlib import Path

def count_email_metrics():
    data_path = Path(__file__).parent.parent.parent / 'data' / 'email_conversations.json'
    with open(data_path, 'r') as f:
        conversations = json.load(f)
    
    total_conversations = len(conversations)
    total_messages = sum(len(conv['Messages']) for conv in conversations)
    
    multi_message_convs = sum(1 for conv in conversations if len(conv['Messages']) > 1)
    single_message_convs = total_conversations - multi_message_convs
    
    print(f"Total number of conversations: {total_conversations}")
    print(f"Total number of messages across all conversations: {total_messages}")
    print(f"Number of conversations with more than 1 message: {multi_message_convs}")
    print(f"Number of conversations with exactly 1 message: {single_message_convs}")

if __name__ == "__main__":
    count_email_metrics()