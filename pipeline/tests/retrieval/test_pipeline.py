from typing import Dict, List
from tabulate import tabulate
from ...retrieval.pipeline import RetrievalPipeline, RetrieverType
from ...retrieval.processor import ConversationGroup

def format_boost_string(result: Dict) -> str:
    """Format boost information into a readable string"""
    if "boosts" not in result:
        return "No boosts"
    
    boost_strs = []
    for boost in result["boosts"]:
        if boost == "company_match":
            boost_strs.append("Company=2.0x")
        elif boost == "temporal_match":
            boost_strs.append("Time=1.5x")
        elif boost == "content_match":
            boost_strs.append("Content=1.0x")
    return ", ".join(boost_strs)

def display_conversation_results(conversation_groups: Dict[str, ConversationGroup], retriever_name: str):
    """Display results grouped by conversation"""
    print(f"\n{'='*40} {retriever_name} Conversation Results {'='*40}")
    
    # Sort conversations by max score
    sorted_convs = sorted(
        conversation_groups.values(),
        key=lambda x: x.max_score,
        reverse=True
    )
    
    # Prepare table rows
    rows = []
    for conv in sorted_convs[:5]:  # Show top 5 conversations
        # Get first chunk for conversation metadata
        first_chunk = conv.chunks[0]
        rows.append([
            f"{conv.max_score:.3f}",
            conv.conversation_id,
            first_chunk["metadata"].get("subject", "")[:50],
            str(len(conv.chunks)),
            format_boost_string(first_chunk)
        ])
    
    # Print table
    print(tabulate(
        rows,
        headers=["Max Score", "Conversation ID", "Subject", "# Chunks", "Boosts"],
        tablefmt="pretty"
    ))

def display_chunk_results(results: List[Dict], retriever_name: str):
    """Display individual chunk results"""
    print(f"\n{'='*40} {retriever_name} Chunk Results {'='*40}")
    
    # Prepare table rows
    rows = []
    for r in results[:10]:  # Show top 10 chunks
        rows.append([
            f"{r.get('vector_score', 0):.3f}",
            f"{r.get('combined_score', 0):.3f}",
            format_boost_string(r),
            r["metadata"].get("conversation_id", ""),
            r["metadata"].get("subject", "")[:30],
            r["metadata"].get("sender_email", "")[:25],
            r["metadata"].get("date", ""),
            r["text"][:25]
        ])
    
    # Print table
    print(tabulate(
        rows,
        headers=["Vector Score", "Combined Score", "Boosts", "Conv ID", "Subject", "Sender", "Date", "Text Preview"],
        tablefmt="pretty"
    ))

def test_pipeline():
    """Test the retrieval pipeline with different configurations"""
    # Initialize pipeline
    pipeline = RetrievalPipeline()
    
    # Test query
    query = "Summarize Shin-Etsu Chemical's actions regarding its share repurchase and tender offer in early 2025."
    print(f"\n{'='*40} Test Query {'='*40}")
    print(query)
    
    # Test each retriever type
    for retriever_type in ["vector", "weighted", "multiplicative"]:
        print(f"\n{'='*40} Testing {retriever_type} retriever {'='*40}")
        
        # Test conversation-level retrieval
        print("\nTesting conversation-level retrieval:")
        result = pipeline.retrieve(
            query=query,
            retriever_type=retriever_type,
            return_conversations=True,
            top_k=5
        )
        
        # Display query analysis if available
        if result.analysis:
            print(f"\n{'='*40} Query Analysis {'='*40}")
            print(f"Company: {result.analysis.company_info.name} (confidence: {result.analysis.company_info.confidence:.2f})")
            print(f"Variations: {result.analysis.company_info.variations}")
            
            temporal = []
            if result.analysis.temporal_info.years:
                temporal.append(f"Years: {result.analysis.temporal_info.years}")
            if result.analysis.temporal_info.months:
                temporal.append(f"Months: {result.analysis.temporal_info.months}")
            if result.analysis.temporal_info.quarter and result.analysis.temporal_info.quarter.is_complete:
                temporal.append(f"Q{result.analysis.temporal_info.quarter.number} {result.analysis.temporal_info.quarter.year}")
            print(f"Temporal: {', '.join(temporal)} (confidence: {result.analysis.temporal_info.confidence:.2f})")
            
            content = []
            if result.analysis.content_info.domain:
                content.append(f"Domain: {result.analysis.content_info.domain}")
            if result.analysis.content_info.action_type:
                content.append(f"Action: {result.analysis.content_info.action_type}")
            if result.analysis.content_info.key_terms:
                content.append(f"Terms: {result.analysis.content_info.key_terms}")
            print(f"Content: {', '.join(content)} (confidence: {result.analysis.content_info.confidence:.2f})")
        
        # Display conversation results
        display_conversation_results(result.conversation_groups, f"{retriever_type} (Conversations)")
        
        # Test chunk-level retrieval
        print("\nTesting chunk-level retrieval:")
        result = pipeline.retrieve(
            query=query,
            retriever_type=retriever_type,
            return_conversations=False,
            top_k=10
        )
        
        # Display chunk results
        display_chunk_results(result.top_chunks, f"{retriever_type} (Chunks)")

if __name__ == "__main__":
    test_pipeline()
