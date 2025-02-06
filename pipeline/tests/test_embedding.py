import json
from pathlib import Path
from rich.console import Console
from rich.table import Table

from pipeline.chunking.conversation_processor import ConversationProcessor
from pipeline.chunking.document_chunker import DocumentChunker
from pipeline.chunking.embed import EmailEmbedder

console = Console()

def test_single_conversation(conversation_index: int = 139):
    """Test embedding pipeline with a single conversation"""
    # Load the conversation
    data_path = Path(__file__).parent.parent.parent / 'data' / 'processed_emails' / 'included_emails.json'
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        conversation = data[conversation_index]['conversation']
    
    # Process the conversation
    processor = ConversationProcessor(dataset="email")
    chunker = DocumentChunker("email")
    embedder = EmailEmbedder(index_name="test_emails")
    
    # Clear any existing test data
    embedder.store.clear_index()
    
    # Process and chunk
    chunks = list(processor.process_conversation(conversation))
    
    # Embed chunks
    embedder.embed_chunks(chunks)
    
    # Verify embeddings
    doc_count = embedder.store.count_documents()
    
    # Get a sample document
    results = embedder.store.client.search(
        index=embedder.store.index_name,
        body={
            "query": {"match_all": {}},
            "size": 1,
            "_source": ["text", "metadata"]
        }
    )
    
    # Display results
    console.print("\n[bold green]Embedding Test Results:[/bold green]")
    
    # Summary table
    summary = Table(title="Summary")
    summary.add_column("Metric", style="cyan")
    summary.add_column("Value", style="green")
    summary.add_row("Total Chunks Created", str(len(chunks)))
    summary.add_row("Total Embeddings", str(doc_count))
    summary.add_row("Storage Location", embedder.store.index_name)
    console.print(summary)
    
    # Content and Metadata Sample
    if results['hits']['hits']:
        sample_table = Table(title="Sample Document (First Chunk)")
        sample_table.add_column("Field", style="cyan")
        sample_table.add_column("Value", style="green", no_wrap=False)
        
        # Get the first hit
        hit = results['hits']['hits'][0]['_source']
        
        # Show document content preview
        content = hit.get('text', '')
        content_preview = content[:200] + "..." if len(content) > 200 else content
        sample_table.add_row("Content Preview", content_preview)
        
        # Show all metadata fields
        metadata = hit.get('metadata', {})
        for key, value in metadata.items():
            sample_table.add_row(f"Metadata: {key}", str(value))
            
        console.print(sample_table)
    
    return results

if __name__ == "__main__":
    test_single_conversation()
