"""Full RAG pipeline combining retrieval and generation."""
from typing import Dict, Any, List
import json
from ..retrieval.pipeline import RetrievalPipeline
from .context_builder import ContextBuilder
from .generator import Generator

def get_chunk_content(result, chunk_id: str) -> Dict[str, Any]:
    """Get original chunk content from chunk ID.
    
    Args:
        result: RetrievalResult object
        chunk_id: Numeric chunk index as string
        
    Returns:
        Dictionary with chunk content and metadata
    """
    try:
        chunk_idx = int(chunk_id)
        
        # Search all conversations for the chunk
        for conv in result.conversation_groups.values():
            for chunk in conv.chunks:
                if chunk['metadata'].get('chunk_index') == chunk_idx:
                    return chunk
    except ValueError:
        print(f"Invalid chunk ID format (must be numeric): {chunk_id}")
    except Exception as e:
        print(f"Error getting chunk content: {e}")
    return None

def run_full_pipeline(
    query: str,
    retriever_type: str = "weighted",
    max_tokens: int = 10000,
    top_k: int = 15
) -> Dict[str, Any]:
    """Run the full RAG pipeline from query to response.
    
    Args:
        query: User query
        retriever_type: Type of retriever to use
        max_tokens: Max tokens for context
        top_k: Number of conversations to retrieve
        
    Returns:
        Dictionary containing:
        - thought_process: List of reasoning steps
        - response: Generated response
        - used_chunks: List of chunks used with their content
    """
    # 1. Retrieve relevant conversations
    pipeline = RetrievalPipeline()
    result = pipeline.retrieve(
        query=query,
        retriever_type=retriever_type,
        return_conversations=True,
        top_k=top_k
    )
    
    # 2. Build context
    builder = ContextBuilder(max_tokens=max_tokens)
    context = builder.build(result)
    
    # 3. Generate response
    generator = Generator()
    llm_response = generator.invoke({
        "query": query,
        "context": context
    })
    
    # 4. Process response
    if not llm_response:
        return {
            "error": "Failed to generate valid response",
            "thought_process": [],
            "response": "",
            "used_chunks": []
        }
    
    # 5. Get used chunks
    used_chunks = []
    for chunk_id, reason in llm_response["answer"].items():
        chunk = get_chunk_content(result, chunk_id)
        if chunk:
            used_chunks.append({
                "chunk_id": chunk_id,
                "reason": reason,
                "content": chunk["text"],
                "metadata": chunk["metadata"]
            })
    
    return {
        "thought_process": llm_response["thought_process"],
        "response": llm_response["response"],
        "used_chunks": used_chunks
    }
