"""Unified pipeline combining retrieval and generation steps."""
from typing import Dict, Any, List, Optional, Literal
from .retrieval.analyzer import QueryAnalyzer
from .retrieval.filter_builder import ElasticsearchFilterBuilder
from .retrieval.retrievers import VectorRetriever, WeightedAverageRetriever
from .retrieval.processor import ConversationProcessor
from .retrieval.schema import RetrievalResult
from .generation.context_builder import ContextBuilder
from .generation.generator import Generator
from .common.store import EmailStore

RetrieverType = Literal["basic", "advanced"]

def analyze_query(query: str) -> Dict[str, Any]:
    """Analyze query and build filter if needed.
    
    Args:
        query: User query string
        
    Returns:
        Dictionary containing query and optional analysis/filter
    """
    try:
        analyzer = QueryAnalyzer()
        filter_builder = ElasticsearchFilterBuilder()
        
        # Run analysis
        analysis = analyzer.invoke(query)
        
        # Build result dict
        result = {"query": query}
        if analysis:
            result["analysis"] = analysis
            result["filter_dict"] = filter_builder.build_filter(analysis)
            
        return result
    except Exception as e:
        print(f"Warning: Query analysis failed: {e}")
        return {"query": query}

def retrieve_content(
    query_info: Dict[str, Any],
    retriever_type: RetrieverType = "advanced",
    k: int = 100
) -> Dict[str, Any]:
    """Retrieve relevant content using specified retriever.
    
    Args:
        query_info: Dict containing query and optional analysis/filter
        retriever_type: Type of retriever to use
        k: Number of results to retrieve
        
    Returns:
        Dictionary containing query and retrieval results
    """
    store = EmailStore()
    
    if retriever_type == "basic":
        retriever = VectorRetriever(store=store)
        results = retriever.retrieve(query=query_info["query"], k=k)
    else:
        retriever = WeightedAverageRetriever(store=store)
        results = retriever.retrieve(
            query=query_info["query"],
            analysis=query_info.get("analysis"),
            filter_dict=query_info.get("filter_dict"),
            k=k
        )
    
    return {
        "query": query_info["query"],
        "results": results
    }

def process_results(
    retrieval_output: Dict[str, Any],
    return_conversations: bool = True,
    top_k: int = 15
) -> RetrievalResult:
    """Process retrieval results into conversations/chunks.
    
    Args:   
        retrieval_output: Output from retrieve_content
        return_conversations: Whether to return conversations or chunks
        top_k: Number of top results to return
        
    Returns:
        RetrievalResult object
    """
    processor = ConversationProcessor()
    
    # Group conversations
    conversation_groups = processor.group_conversations(retrieval_output["results"])
    
    # Create result object
    result = RetrievalResult(query=retrieval_output["query"])
    result.conversation_groups = conversation_groups
    
    if return_conversations:
        # Return top conversations with their chunks
        result.top_conversations = processor.select_top_conversations(conversation_groups)
        if top_k:
            result.top_conversations = result.top_conversations[:top_k]
    else:
        # Return top individual chunks
        all_chunks = []
        for group in conversation_groups.values():
            all_chunks.extend(group.chunks)
        result.top_chunks = sorted(
            all_chunks,
            key=lambda x: x.get("combined_score", x.get("vector_score", 0)),
            reverse=True
        )[:top_k] if top_k else all_chunks
    
    return result

def get_chunk_content(result: RetrievalResult, chunk_id: str) -> Optional[Dict[str, Any]]:
    """Get original chunk content from chunk ID."""
    try:
        chunk_idx = int(chunk_id)
        for conv in result.conversation_groups.values():
            for chunk in conv.chunks:
                if chunk['metadata'].get('chunk_index') == chunk_idx:
                    return chunk
    except ValueError:
        print(f"Invalid chunk ID format (must be numeric): {chunk_id}")
    except Exception as e:
        print(f"Error getting chunk content: {e}")
    return None

def generate_response(
    query: str,
    retrieval_result: RetrievalResult,
    max_tokens: int = 10000
) -> Dict[str, Any]:
    """Generate response using retrieved context.
    
    Args:
        query: Original query string
        retrieval_result: Result from process_results
        max_tokens: Max tokens for context building
        
    Returns:
        Dictionary containing response, thought process, and used chunks
    """
    # Build context
    builder = ContextBuilder(max_tokens=max_tokens)
    context = builder.build(retrieval_result)


    # Generate response
    generator = Generator()
    llm_response = generator.invoke({
        "query": query,
        "context": context
    })
    
    if not llm_response:
        return {
            "error": "Failed to generate valid response",
            "thought_process": [],
            "response": "",
            "used_chunks": []
        }
    
    # Get used chunks
    used_chunks = []
    for chunk_id, reason in llm_response["answer"].items():
        chunk = get_chunk_content(retrieval_result, chunk_id)
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

def run_pipeline(
    query: str,
    retriever_type: RetrieverType = "advanced",
    return_conversations: bool = True,
    top_k: int = 15,
    max_tokens: int = 10000
) -> Dict[str, Any]:
    """Run the complete pipeline from query to response.
    
    Args:
        query: User query string
        retriever_type: Type of retriever to use
        return_conversations: Whether to return conversations or chunks
        top_k: Number of top results to return
        max_tokens: Max tokens for context building
        
    Returns:
        Dictionary containing final response and metadata
    """
    # 1. Analyze query and build filter if using advanced retriever
    if retriever_type == "advanced":
        query_info = analyze_query(query)
    else:
        query_info = {"query": query}
    
    # 2. Retrieve relevant content
    retrieval_output = retrieve_content(
        query_info,
        retriever_type=retriever_type,
        k=100  # Get more results initially for better grouping
    )
    
    # 3. Process and group results
    retrieval_result = process_results(
        retrieval_output,
        return_conversations=return_conversations,
        top_k=top_k
    )
    
    # 4. Generate final response
    final_output = generate_response(
        query,
        retrieval_result,
        max_tokens=max_tokens
    )
    
    return final_output

if __name__ == "__main__":
    print(run_pipeline("Summarize the reports on Samsung SDS over the past 3 quarter"))