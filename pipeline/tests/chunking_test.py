import json
from pathlib import Path
from typing import Dict, List, Generator
import typer
from rich.console import Console
from rich.table import Table

from pipeline.chunking.conversation_processor import ConversationProcessor
from pipeline.chunking.base import Chunk

app = typer.Typer()
console = Console()

CONVERSATIONS_PATH = Path(__file__).parent.parent.parent / 'data' / 'processed_emails' / 'included_emails.json'
BASE_DIR = Path(__file__).parent.parent.parent / 'data'

def load_test_conversations() -> List[Dict]:
    """Load test conversations from the data directory."""
    with open(CONVERSATIONS_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
        # Extract conversation data from the nested structure
        return [item['conversation'] for item in data]

def display_chunk_info(chunk: Chunk, index: int):
    """Display information about a chunk in a formatted table"""
    table = Table(title=f"Chunk {index}")
    
    # Add columns
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")
    
    # Add content length and preview
    content_preview = chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content
    table.add_row("Content Length", str(len(chunk.content)))
    table.add_row("Content Preview", content_preview)
    
    # Add metadata
    metadata = chunk.metadata
    table.add_row("Chunk Type", metadata.chunk_type)
    table.add_row("Conversation ID", metadata.conversation_id)
    table.add_row("Subject", metadata.subject)
    table.add_row("Sender", f"{metadata.sender_name} ({metadata.sender_email})")
    table.add_row("Year", str(metadata.year))
    table.add_row("Month", str(metadata.month))
    table.add_row("Day", str(metadata.day))
    table.add_row("Chunk Index", str(metadata.chunk_index))
    table.add_row("Total Chunks", str(metadata.total_chunks))
    
    # Add attachment metadata if present
    if hasattr(metadata, 'attachment_metadata') and metadata.attachment_metadata:
        table.add_row("File Name", metadata.attachment_metadata.get('file_name', ''))
        table.add_row("File Type", metadata.attachment_metadata.get('extension', ''))
        table.add_row("Document Type", metadata.attachment_metadata.get('document_type', ''))
        
        # Add other attachment-specific metadata
        for key, value in metadata.attachment_metadata.items():
            if key not in ['file_name', 'extension', 'document_type']:
                table.add_row(f"Attachment {key}", str(value))
    
    console.print(table)
    console.print("\n")

def test_conversation_chunking(index: int = 0) -> Generator[Chunk, None, None]:
    """Test chunking for a specific conversation."""
    conversations = load_test_conversations()
    
    if index >= len(conversations):
        raise ValueError(f"Index {index} is out of range. Only {len(conversations)} conversations available.")
    
    processor = ConversationProcessor(dataset="test", base_dir=str(BASE_DIR))
    return processor.process_conversation(conversations[index])

def analyze_chunks(chunks: List[Chunk]):
    """Analyze and display statistics about chunks"""
    stats_table = Table(title="Chunking Statistics")
    stats_table.add_column("Metric", style="cyan")
    stats_table.add_column("Value", style="green")
    
    # Collect statistics
    total_chunks = len(chunks)
    chunk_types = {}
    avg_chunk_size = sum(len(chunk.content) for chunk in chunks) / total_chunks if total_chunks > 0 else 0
    
    for chunk in chunks:
        chunk_type = chunk.metadata.chunk_type
        chunk_types[chunk_type] = chunk_types.get(chunk_type, 0) + 1
    
    # Add statistics to table
    stats_table.add_row("Total Chunks", str(total_chunks))
    stats_table.add_row("Average Chunk Size", f"{avg_chunk_size:.2f} characters")
    
    for chunk_type, count in chunk_types.items():
        stats_table.add_row(f"Number of {chunk_type} chunks", str(count))
    
    console.print(stats_table)
    console.print("\n")

def find_conversations_with_attachments():
    """Find and print conversations that have attachments."""
    conversations = load_test_conversations()
    
    console.print("\n[bold cyan]Conversations with attachments:[/bold cyan]")
    console.print("=" * 80)
    
    for idx, conv in enumerate(conversations):
        has_attachments = False
        for message in conv['Messages']:
            if 'AttachmentFiles' in message and message['AttachmentFiles']:
                has_attachments = True
                console.print(f"\n[bold]Index {idx}:[/bold]")
                console.print(f"Subject: {message['Subject']}")
                console.print(f"From: {message['SenderName']} ({message['SenderEmail']})")
                console.print("Attachments:")
                for att in message['AttachmentFiles']:
                    console.print(f"- {Path(att).suffix}: {att}")
                break
        
        if has_attachments:
            console.print("-" * 80)

@app.command()
def main(
    index: int = typer.Argument(0, help="Index of the conversation to process"),
    show_chunks: bool = typer.Option(True, "--show-chunks", help="Show individual chunks"),
    show_stats: bool = typer.Option(True, "--show-stats", help="Show chunking statistics"),
    list_attachments: bool = typer.Option(False, "--list-attachments", help="List all conversations with attachments")
):
    """Test the document chunking system."""
    try:
        if list_attachments:
            find_conversations_with_attachments()
            return
            
        # Process chunks
        chunks = list(test_conversation_chunking(index))
        
        if show_stats:
            analyze_chunks(chunks)
            
        if show_chunks:
            for i, chunk in enumerate(chunks):
                display_chunk_info(chunk, i)
                
    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")

if __name__ == "__main__":
    app()
