from typing import Dict, List, Any
from dataclasses import dataclass

@dataclass
class ConversationGroup:
    chunks: List[Dict]
    max_score: float
    conversation_id: str

class ConversationProcessor:
    def __init__(self, max_chunk_length: int = 1000):
        self.max_chunk_length = max_chunk_length

    def group_conversations(
        self,
        chunks: List[Dict]
    ) -> Dict[str, ConversationGroup]:
        """Group chunks by conversation and fetch all related chunks"""
        from ..common.store import EmailStore
        store = EmailStore()
        
        # First create a map of chunk text to scores from search results
        chunk_scores = {}
        for chunk in chunks:
            chunk_scores[chunk['text']] = {
                'combined_score': chunk.get('combined_score', 0),
                'vector_score': chunk.get('vector_score', 0)
            }
        
        conversation_groups = {}
        conv_ids_seen = set()
        
        for chunk in chunks:
            conv_id = chunk['metadata']['conversation_id']
            if conv_id in conv_ids_seen:
                continue
                
            conv_ids_seen.add(conv_id)
            
            # Get ALL chunks for this conversation from the store
            all_conv_chunks = store.get_chunks_by_conversation_id(conv_id)
            
            # Update scores for chunks that were in search results
            for c in all_conv_chunks:
                if c['text'] in chunk_scores:
                    scores = chunk_scores[c['text']]
                    c['combined_score'] = scores['combined_score']
                    c['vector_score'] = scores['vector_score']
                # Other chunks keep their zero scores from store
            
            # Create group with all chunks
            conversation_groups[conv_id] = ConversationGroup(
                chunks=all_conv_chunks,
                max_score=chunk.get('combined_score', 0),
                conversation_id=conv_id
            )
        
        return conversation_groups

    def process_conversation(
        self,
        conv_group: ConversationGroup
    ) -> List[Dict]:
        """Process a conversation group with smart truncation"""
        # Sort chunks by index to maintain order
        conv_group.chunks.sort(
            key=lambda x: x['metadata']['chunk_index']
        )
        
        processed_chunks = []
        for chunk in conv_group.chunks:
            # Keep chunks with high scores at full length
            if chunk['combined_score'] > 0.7:
                processed_chunks.append(chunk)
            else:
                # Truncate low-scoring chunks
                truncated = self._truncate_chunk(chunk)
                processed_chunks.append(truncated)
        
        return processed_chunks

    def _truncate_chunk(self, chunk: Dict) -> Dict:
        """Truncate chunk content while preserving metadata"""
        text = chunk['text']
        if len(text) <= self.max_chunk_length:
            return chunk
            
        # Create truncated version
        truncated = {
            **chunk,
            'text': text[:self.max_chunk_length] + "..."
        }
        
        return truncated

    def select_top_conversations(
        self,
        conversation_groups: Dict[str, ConversationGroup],
        max_conversations: int = 5
    ) -> List[Dict]:
        """Select and process top conversations"""
        # Sort conversations by max score
        sorted_convs = sorted(
            conversation_groups.values(),
            key=lambda x: x.max_score,
            reverse=True
        )
        
        # Process top conversations
        final_results = []
        for conv_group in sorted_convs[:max_conversations]:
            processed_chunks = self.process_conversation(conv_group)
            final_results.extend(processed_chunks)
        
        return final_results
