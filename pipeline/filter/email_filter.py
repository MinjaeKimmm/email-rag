"""Module for filtering email conversations based on message count."""

def split_conversations_by_message_count(conversations):
    """
    Split conversations into single-message and multi-message groups.
    
    Args:
        conversations: List of conversation dictionaries
        
    Returns:
        tuple: (single_message_conversations, multi_message_conversations)
    """
    # Split conversations
    single_message_convs = [conv for conv in conversations if len(conv['Messages']) == 1]
    multi_message_convs = [conv for conv in conversations if len(conv['Messages']) > 1]
    
    return single_message_convs, multi_message_convs