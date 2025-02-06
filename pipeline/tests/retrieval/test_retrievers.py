import argparse
from typing import Dict, List
from tabulate import tabulate
from langchain.schema.runnable import RunnablePassthrough
from ...common.store import EmailStore
from ...retrieval.retrievers import VectorRetriever, WeightedAverageRetriever, MultiplicativeRetriever
from ...retrieval.analyzer import QueryAnalyzer
from ...retrieval.filter_builder import ElasticsearchFilterBuilder
from ...retrieval.schema import QueryAnalysis
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

def test_retrievers(query: str):
    """Test and compare different retriever implementations"""
    # Initialize components
    store = EmailStore()
    
    # Create retrievers and chains
    vector_retriever = VectorRetriever(store=store)
    weighted_retriever = WeightedAverageRetriever(store=store)
    multiplicative_retriever = MultiplicativeRetriever(store=store)
    
    # Create analyzer and filter builder
    query_analyzer = QueryAnalyzer()
    filter_builder = ElasticsearchFilterBuilder()
    
    # Print query
    print(f"\n{'='*40} Test Query {'='*40}")
    print(query)
    
    # Run query analysis
    analysis = query_analyzer.invoke(query)
    print(f"\n{'='*40} Query Analysis {'='*40}")
    print(f"Company: {analysis.company_info.name} (confidence: {analysis.company_info.confidence:.2f})")
    print(f"Variations: {analysis.company_info.variations}")
    
    temporal = []
    if analysis.temporal_info.years:
        temporal.append(f"Years: {analysis.temporal_info.years}")
    if analysis.temporal_info.months:
        temporal.append(f"Months: {analysis.temporal_info.months}")
    if analysis.temporal_info.quarter and analysis.temporal_info.quarter.is_complete:
        temporal.append(f"Q{analysis.temporal_info.quarter.number} {analysis.temporal_info.quarter.year}")
    print(f"Temporal: {', '.join(temporal)} (confidence: {analysis.temporal_info.confidence:.2f})")
    
    content = []
    if analysis.content_info.domain:
        content.append(f"Domain: {analysis.content_info.domain}")
    if analysis.content_info.action_type:
        content.append(f"Action: {analysis.content_info.action_type}")
    if analysis.content_info.key_terms:
        content.append(f"Terms: {analysis.content_info.key_terms}")
    print(f"Content: {', '.join(content)} (confidence: {analysis.content_info.confidence:.2f})")
    
    # Build filter
    filter_dict = filter_builder.build_filter(analysis)
    print(f"\n{'='*40} Filter {'='*40}")
    print(filter_dict)
    
    # Create chains for each retriever
    # Vector-only chain (no query analysis)
    vector_chain = RunnablePassthrough() | {"results": lambda x: vector_retriever.retrieve(x)}
    
    # Weighted chain with query analysis
    weighted_chain = (
        RunnablePassthrough()
        | {"query": lambda x: x}
        | {
            "query": lambda x: x["query"],
            "analysis": lambda x: analysis
        }
        | {"results": lambda x: weighted_retriever.retrieve(x["query"], x["analysis"])}
    )
    
    # Multiplicative chain with query analysis
    multiplicative_chain = (
        RunnablePassthrough()
        | {"query": lambda x: x}
        | {
            "query": lambda x: x["query"],
            "analysis": lambda x: analysis
        }
        | {"results": lambda x: multiplicative_retriever.retrieve(x["query"], x["analysis"])}
    )
    
    # Run chains
    vector_output = vector_chain.invoke(query)
    weighted_output = weighted_chain.invoke(query)
    multiplicative_output = multiplicative_chain.invoke(query)
    
    
    # Process conversations
    from ...retrieval.processor import ConversationProcessor
    processor = ConversationProcessor()
    
    # Process each retriever's results
    vector_convs = processor.group_conversations(vector_output["results"])
    vector_results = processor.select_top_conversations(vector_convs)
    
    weighted_convs = processor.group_conversations(weighted_output["results"])
    weighted_results = processor.select_top_conversations(weighted_convs)
    
    multiplicative_convs = processor.group_conversations(multiplicative_output["results"])
    multiplicative_results = processor.select_top_conversations(multiplicative_convs)
    
    # Display conversation-level results
    display_conversation_results(vector_convs, "Vector-Only")
    display_conversation_results(weighted_convs, "Weighted Average") 
    display_conversation_results(multiplicative_convs, "Multiplicative")
    
    # Display chunk-level results
    display_chunk_results(vector_results, "Vector-Only")
    display_chunk_results(weighted_results, "Weighted Average") 
    display_chunk_results(multiplicative_results, "Multiplicative")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("query_index", type=int, help="Index of the test query to use")
    args = parser.parse_args()
    
    # Test queries
    test_queries = [
        "Summarize Shin-Etsu Chemical's actions regarding its share repurchase and tender offer in early 2025.",
        # Add more test queries here
    ]
    
    if args.query_index >= len(test_queries):
        print(f"Error: query_index {args.query_index} is out of range. Max index is {len(test_queries)-1}")
        exit(1)
        
    test_retrievers(test_queries[args.query_index])
