"""Script to demonstrate the complete retrieval flow"""
from pipeline.retrieval.pipeline import RetrievalPipeline
import json
import argparse

def show_retrieval_flow(query=None, index=None):
    """Demonstrate the complete retrieval flow with weighted retriever
    
    Args:
        query (str, optional): Direct query to process
        index (int, optional): Index of QA pair to use from qa_pairs.json
    """
    # Initialize pipeline
    pipeline = RetrievalPipeline()
    
    # Determine query source
    if query is None and index is not None:
        # Load query from qa_pairs.json
        with open("data/qa_pairs.json", 'r') as f:
            qa_pairs = json.load(f)
        
        qa_pair = qa_pairs[index]
        query = qa_pair["Question"]
        print("\n1. Query (from qa_pairs[{}]):".format(index))
        print(query)
        print("\nGround Truth Conversation ID:")
        print(qa_pair["Conversation_ID"])
    elif query is not None:
        print("\n1. Direct Query:")
        print(query)
    else:
        raise ValueError("Either query or index must be provided")
    
    
    # First get query analysis
    result = pipeline.retrieve(
        query=query,
        retriever_type="weighted",
        return_conversations=True,
        top_k=15  # Limiting to 3 for clarity
    )
    
    # Print analysis if available
    print("\n2. Query Analysis:")
    if result.analysis:
        analysis_dict = {
            "company_info": {
                "name": result.analysis.company_info.name,
                "variations": result.analysis.company_info.variations,
                "confidence": result.analysis.company_info.confidence
            },
            "temporal_info": {
                "years": result.analysis.temporal_info.years,
                "months": result.analysis.temporal_info.months,
                "quarter": {
                    "number": result.analysis.temporal_info.quarter.number,
                    "year": result.analysis.temporal_info.quarter.year,
                    "is_complete": result.analysis.temporal_info.quarter.is_complete
                } if result.analysis.temporal_info.quarter else None,
                "confidence": result.analysis.temporal_info.confidence
            },
            "content_info": {
                "domain": result.analysis.content_info.domain,
                "action_type": result.analysis.content_info.action_type,
                "key_terms": result.analysis.content_info.key_terms,
                "confidence": result.analysis.content_info.confidence
            }
        }
        print(json.dumps(analysis_dict, indent=2))
    else:
        print("No query analysis available (using vector retriever)")
    
    # Get the filter that was built from the analysis (if any)
    print("\n3. Generated Elasticsearch Filter:")
    if result.analysis:
        filter_dict = pipeline.filter_builder.build_filter(result.analysis)
        print(json.dumps(filter_dict, indent=2))
    else:
        print("No filter generated (using vector retriever)")
    

    # Show how context would be built for LLM
    print("\n6. Final Context Building:")
    
    from pipeline.generation import ContextBuilder
    builder = ContextBuilder(max_tokens=10000)
    context = builder.build(result)
    
    print(f"\nContext Statistics:")
    print(f"Total Tokens: {context.total_tokens}")
    print(f"Number of Conversations: {context.num_conversations}")
    print(f"Number of Chunks: {context.num_chunks}")
    print(f"  - Full Length Chunks: {context.num_full_chunks}")
    print(f"  - Truncated Chunks: {context.num_truncated_chunks}")
    
    print("\n7. Final Generation:")
    from pipeline.generation.generator import Generator
    
    # Create generator and get prompt
    generator = Generator()
    prompt = generator.get_prompt({"query": query, "context": context})
    
    print("\nFinal Prompt:")
    print(prompt[:1000])
    with open("pipeline/tests/retrieval/prompt.txt", "w", encoding="utf-8") as f:
        f.write(prompt)
    print("\nFull prompt saved to prompt.txt")
    
    # Generate response
    response = generator.invoke({"query": query, "context": context})
    
    if not response:
        print("\nError: Failed to generate valid response")
        return
        
    print("\nThought Process:")
    for step in response["thought_process"]:
        print(f"- {step}")
    
    print("\nResponse:")
    print(response["response"])
    
    print("\nUsed Chunks:")
    for chunk_id, reason in response["answer"].items():
        print(f"\nChunk {chunk_id}:")
        print(f"Reason: {reason}")



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Demonstrate retrieval pipeline flow')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--query', type=str, help='Direct query to process')
    group.add_argument('--index', type=int, help='Index of QA pair to use from qa_pairs.json')
    
    args = parser.parse_args()
    show_retrieval_flow(query=args.query, index=args.index)