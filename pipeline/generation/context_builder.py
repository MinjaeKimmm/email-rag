"""Build context from retrieved conversations for LLM generation."""
from typing import Dict, List, Tuple
from dataclasses import dataclass
from ..retrieval.schema import RetrievalResult

@dataclass
class GenerationContext:
    """Context prepared for LLM generation"""
    context_text: str
    chunk_ids: List[str]  # List of available chunk IDs
    total_tokens: int
    num_conversations: int
    num_chunks: int
    num_full_chunks: int  # Chunks shown at full length
    num_truncated_chunks: int  # Chunks that were truncated

class ContextBuilder:
    def __init__(self, max_tokens: int = 6000):
        self.max_tokens = max_tokens
        self.top_chunk_length = 3000
        self.bottom_chunk_length = 300
        self.max_conversations = 15  # Maximum number of conversations to include
    
    def _format_chunk(self, chunk: Dict, show_metadata: bool = True, length: int = None) -> Tuple[str, str]:
        """Format a chunk with optional metadata and length limit
        
        Returns:
            Tuple of (formatted_text, chunk_id)
        """
        metadata = chunk['metadata']
        formatted = []
        
        # Generate chunk ID (just use chunk_index)
        chunk_id = str(metadata.get('chunk_index'))
        
        # Only show metadata for first chunk in conversation
        if show_metadata:
            formatted.extend([
                f"[Subject: {metadata.get('subject', 'N/A')}]",
                f"[From: {metadata.get('sender_name', 'N/A')} <{metadata.get('sender_email', 'N/A')}>]",
                f"[Date: {metadata.get('year', 'N/A')}-{metadata.get('month', 'N/A')}-{metadata.get('day', 'N/A')}]",
                f"[Chunk: {chunk_id}]"
            ])
        else:
            formatted.append(f"[Chunk: {chunk_id}]")
        
        # Different headers for email body vs attachments
        chunk_type = metadata.get('chunk_type', '')
        if chunk_type == 'email_body':
            formatted.append("[Email Body Content:]")
        else:
            # Could be pdf, xlsx, etc.
            formatted.append(f"[{chunk_type.upper()} Content:]")
        
        # Truncate content if length specified
        text = chunk['text']
        if length and len(text) > length:
            text = text[:length] + "..."
        formatted.append(text)
        formatted.append("")
        
        return "\n".join(formatted), chunk_id
    
    def _estimate_conversation_tokens(self, chunks: List[Dict]) -> Tuple[int, Dict]:
        """Estimate tokens for a conversation with proper truncation"""
        # First ensure email_body comes first
        email_body = [c for c in chunks if c['metadata'].get('chunk_type') == 'email_body']
        others = [c for c in chunks if c['metadata'].get('chunk_type') != 'email_body']
        chunks = email_body + sorted(others, key=lambda c: c.get('combined_score', 0), reverse=True)
        
        total_tokens = 0
        chunk_stats = {'full': 0, 'truncated': 0}
        
        # Process first chunk with metadata
        if chunks:
            length = self.top_chunk_length if chunks[0].get('combined_score', 0) > 0 else self.bottom_chunk_length
            formatted_text, _ = self._format_chunk(chunks[0], show_metadata=True, length=length)
            first_tokens = len(formatted_text.split())
            total_tokens += first_tokens
            if chunks[0].get('combined_score', 0) > 0:
                chunk_stats['full'] += 1
            else:
                chunk_stats['truncated'] += 1
        
        # Process remaining chunks
        for chunk in chunks[1:]:
            length = self.top_chunk_length if chunk.get('combined_score', 0) > 0 else self.bottom_chunk_length
            formatted_text, _ = self._format_chunk(chunk, show_metadata=False, length=length)
            tokens = len(formatted_text.split())
            total_tokens += tokens
            if chunk.get('combined_score', 0) > 0:
                chunk_stats['full'] += 1
            else:
                chunk_stats['truncated'] += 1
                
        return total_tokens, chunk_stats
    
    def build(self, result: RetrievalResult) -> GenerationContext:
        """Build context from retrieval result with adaptive length"""
        # Start with top conversations by score
        # Sort conversations by max chunk score
        sorted_convs = sorted(
            result.conversation_groups.values(),
            key=lambda c: max((chunk.get('combined_score', chunk.get('vector_score', 0)) 
                            for chunk in c.get('chunks', [])), default=0),
            reverse=True
        )
        
        # Track which conversations we can include
        total_tokens = 0
        header_tokens = len("=== Conversation X ===".split())
        conversations_to_use = []
        all_chunk_stats = []
        
        # First pass - estimate tokens and collect stats
        for i, conv in enumerate(sorted_convs, 1):
            conv_tokens, chunk_stats = self._estimate_conversation_tokens(conv.get('chunks', []))
            conv_tokens += header_tokens
            
            if total_tokens + conv_tokens > self.max_tokens:
                break
                
            total_tokens += conv_tokens
            conversations_to_use.append(conv)
            all_chunk_stats.append(chunk_stats)
            
            if len(conversations_to_use) >= self.max_conversations:
                break
        
        # Second pass - build actual context
        context_parts = []
        chunk_ids = []
        
        for i, conv in enumerate(conversations_to_use, 1):
            # First ensure email_body comes first
            chunks = conv.get('chunks', [])
            email_body = [c for c in chunks if c['metadata'].get('chunk_type') == 'email_body']
            others = [c for c in chunks if c['metadata'].get('chunk_type') != 'email_body']
            chunks = email_body + sorted(others, key=lambda c: c.get('combined_score', 0), reverse=True)
            
            # Add conversation header
            header = f"\n=== Conversation {i} ==="
            context_parts.append(header)
            
            # Add chunks with proper truncation
            for j, chunk in enumerate(chunks):
                length = self.top_chunk_length if chunk.get('combined_score', 0) > 0 else self.bottom_chunk_length
                formatted_text, chunk_id = self._format_chunk(chunk, show_metadata=j==0, length=length)
                context_parts.append(formatted_text)
                chunk_ids.append(chunk_id)
        
        final_context = "\n".join(context_parts)
        
        return GenerationContext(
            context_text=final_context,
            chunk_ids=chunk_ids,
            total_tokens=total_tokens,
            num_conversations=len(conversations_to_use),
            num_chunks=sum(s['full'] + s['truncated'] for s in all_chunk_stats),
            num_full_chunks=sum(s['full'] for s in all_chunk_stats),
            num_truncated_chunks=sum(s['truncated'] for s in all_chunk_stats)
        )
