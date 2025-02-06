import typer
import json
from typing import Dict
from rich.console import Console
from rich.table import Table
from datetime import datetime

from pipeline.common.store import EmailStore
from pipeline.retrieval.filter_builder import ElasticsearchFilterBuilder
from pipeline.tests.retrieval.test_filter_builder import get_manual_examples

app = typer.Typer()
console = Console()

def get_test_documents():
    """Get test documents and metadata for the search test"""
    documents = [
        # Shin-Etsu Chemical document
        {
            "text": "Shin-Etsu Chemical Co., Ltd. (信越化学工業) announces a share repurchase program and tender offer. The company plans to buy back up to 10 million shares...",
            "metadata": {
                "conversation_id": "shin-etsu-1",
                "subject": "Share Repurchase and Tender Offer Announcement",
                "sender_name": "Shin-Etsu Chemical",
                "sender_email": "ir@shinetsu.jp",
                "year": 2025,
                "month": 1,
                "day": 15,
                "chunk_type": "email_body",
                "chunk_index": 0,
                "total_chunks": 1
            }
        },
        # Another Shin-Etsu document
        {
            "text": "信越化学工業 announces its financial results for Q3 FY2024. The company has shown strong performance...",
            "metadata": {
                "conversation_id": "shin-etsu-2",
                "subject": "Q3 FY2024 Financial Results",
                "sender_name": "信越化学工業",
                "sender_email": "ir@shinetsu.jp",
                "year": 2025,
                "month": 2,
                "day": 1,
                "chunk_type": "email_body",
                "chunk_index": 0,
                "total_chunks": 1
            }
        },
        # Unrelated document
        {
            "text": "Samsung Electronics announces new product launch event scheduled for March 2025...",
            "metadata": {
                "conversation_id": "samsung-1",
                "subject": "Product Launch Announcement",
                "sender_name": "Samsung Electronics",
                "sender_email": "news@samsung.com",
                "year": 2025,
                "month": 1,
                "day": 20,
                "chunk_type": "email_body",
                "chunk_index": 0,
                "total_chunks": 1
            }
        }
    ]
    return documents

@app.command()
def test_search(
    example_idx: int = typer.Argument(..., help="Index of manual example to test"),
    use_filter: bool = typer.Option(False, help="Whether to use metadata filters"),
    use_test_index: bool = typer.Option(False, help="Whether to use test_emails index instead of emails")
):
    """Test vector search with filters using manual examples"""
    # Get example query and expected filter
    examples = get_manual_examples()
    if not 0 <= example_idx < len(examples):
        console.print(f"[red]Error: Invalid example index. Must be between 0 and {len(examples)-1}[/red]")
        return
    
    example = examples[example_idx]
    
    # Initialize store with specified index
    index_name = "test_emails" if use_test_index else "emails"
    store = EmailStore(index_name=index_name)
    
    # Only setup test data if using test index
    if use_test_index:
        store.clear_index()
        test_docs = get_test_documents()
        texts = [doc["text"] for doc in test_docs]
        metadatas = [doc["metadata"] for doc in test_docs]
        store.add_documents(texts=texts, metadatas=metadatas)
    
    # Display query
    console.rule("[bold]Test Query")
    console.print(example.original_query)
    console.print()
    
    # Build and display filter if requested
    filter_dict = None
    if use_filter:
        builder = ElasticsearchFilterBuilder(company_variation_limit=4, content_term_limit=4)
        filter_dict = builder.build_filter(example)
        console.rule("[bold]Elasticsearch Filter")
        console.print(json.dumps(filter_dict, indent=2))
        console.print()
    
    # Perform search
    results = store.similarity_search(
        query=example.original_query,
        filter_dict=filter_dict["query"] if filter_dict else None,
        k=10
    )
    
    # Get vector-only results first
    vector_results = store.similarity_search(
        query=example.original_query,
        filter_dict=None,
        k=10
    )
    
    # Get combined results with filter
    combined_results = None
    if use_filter:
        combined_results = results
    
    # Create lookup of vector scores
    vector_scores = {}
    for doc, score in vector_results:
        key = (doc.metadata['subject'], doc.metadata['sender_name'], doc.page_content[:50])
        vector_scores[key] = score
    
    # Display results
    console.rule("[bold]Search Results")
    table = Table(show_header=True, header_style="bold")
    table.add_column("Vector Score")
    if use_filter:
        table.add_column("Combined Score")
        table.add_column("Boost")
    table.add_column("Subject")
    table.add_column("Sender")
    table.add_column("Date")
    table.add_column("Text Preview")
    
    # Show results based on mode
    results_to_show = combined_results if use_filter else vector_results
    for doc, score in results_to_show:
        metadata = doc.metadata
        date = f"{metadata['year']}-{metadata['month']:02d}-{metadata['day']:02d}"
        text_preview = doc.page_content[:100] + "..." if len(doc.page_content) > 100 else doc.page_content
        
        # Get vector score for this document
        key = (metadata['subject'], metadata['sender_name'], doc.page_content[:50])
        vector_score = vector_scores.get(key, 0.0)
        
        # Calculate boost based on filter matches
        boost_details = []
        total_boost = 1.0
        if use_filter and filter_dict:
            # Check which filter conditions match and sum their boosts
            should_conditions = filter_dict['query']['bool']['should']
            for condition in should_conditions:
                if condition.get('bool', {}).get('boost'):
                    # Add boost if the condition matches the document
                    if _condition_matches_doc(condition['bool'], metadata, doc.page_content):
                        boost_value = condition['bool']['boost']
                        boost_type = 'company' if len(condition['bool'].get('must', [])) == 2 else \
                                    'temporal' if any('terms' in c for c in condition['bool'].get('must', [])) else \
                                    'content'
                        boost_details.append(f"{boost_type}={boost_value}x")
                        total_boost += boost_value - 1.0  # Subtract 1 since boosts are additive
        
        row = [
            f"{vector_score:.3f}",
        ]
        if use_filter:
            row.extend([
                f"{score:.3f}",
                f"{total_boost:.2f}x ({', '.join(boost_details)})"
            ])
        row.extend([
            metadata["subject"],
            metadata["sender_name"],
            date,
            text_preview
        ])
        table.add_row(*row)
    
    console.print(table)

def _condition_matches_doc(bool_clause: Dict, metadata: Dict, content: str) -> bool:
        """Check if a bool clause from the filter matches a document"""
        # Company match
        if 'must' in bool_clause and len(bool_clause['must']) == 2:
            sender_matches = False
            email_matches = False
            for must_clause in bool_clause['must']:
                if 'bool' in must_clause and 'should' in must_clause['bool']:
                    for should_clause in must_clause['bool']['should']:
                        if 'wildcard' in should_clause:
                            field = list(should_clause['wildcard'].keys())[0]
                            pattern = should_clause['wildcard'][field]['value'].replace('*', '')
                            if field == 'metadata.sender_name' and pattern.lower() in metadata['sender_name'].lower():
                                sender_matches = True
                            elif field == 'metadata.sender_email' and pattern.lower() in metadata['sender_email'].lower():
                                email_matches = True
            return sender_matches and email_matches
        
        # Temporal match
        elif 'must' in bool_clause and len(bool_clause['must']) == 1:
            clause = bool_clause['must'][0]
            if 'terms' in clause:
                if 'metadata.year' in clause['terms'] and metadata['year'] in clause['terms']['metadata.year']:
                    return True
                if 'metadata.month' in clause['terms'] and metadata['month'] in clause['terms']['metadata.month']:
                    return True
            return False
        
        # Content match
        elif 'should' in bool_clause:
            for should_clause in bool_clause['should']:
                if 'wildcard' in should_clause:
                    field = list(should_clause['wildcard'].keys())[0]
                    pattern = should_clause['wildcard'][field]['value'].replace('*', '')
                    if field == 'metadata.subject' and pattern.lower() in metadata['subject'].lower():
                        return True
                    elif field == 'text' and pattern.lower() in content.lower():
                        return True
            return False
        
        return False

if __name__ == "__main__":
    app()
