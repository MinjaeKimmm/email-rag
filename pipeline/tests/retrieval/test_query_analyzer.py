from pathlib import Path
import json
from datetime import datetime
import typer
from rich.console import Console
from rich.table import Table
from typing import Dict, List, Optional

from pipeline.retrieval.analyzer import QueryAnalyzer
from pipeline.retrieval.schema import QueryAnalysis
from pipeline.common.settings import LLM

app = typer.Typer()
console = Console()

QA_PAIRS_PATH = Path(__file__).parent.parent.parent.parent / 'data' / 'qa_pairs.json'
INCLUDED_EMAILS_PATH = Path(__file__).parent.parent.parent.parent / 'data' / 'processed_emails' / 'included_emails.json'

def load_test_queries() -> List[Dict]:
    """Load test queries from the qa_pairs.json file."""
    with open(QA_PAIRS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def find_test_case_index(conversation_id: str) -> Optional[int]:
    """Find the index of a test case by its conversation ID."""
    queries = load_test_queries()
    for idx, query in enumerate(queries):
        if query.get("Conversation_ID") == conversation_id:
            return idx
    return None

def load_email_metadata(conversation_id: str) -> Optional[Dict]:
    """Load email metadata for a specific conversation ID."""
    with open(INCLUDED_EMAILS_PATH, 'r', encoding='utf-8') as f:
        emails = json.load(f)
        
    for email in emails:
        if email['conversation_id'] == conversation_id:
            message = email['conversation']['Messages'][0]
            received_time = datetime.strptime(message['ReceivedTime'], '%Y-%m-%d %H:%M:%S')
            
            return {
                'subject': message['Subject'],
                'sender_name': message['SenderName'],
                'sender_email': message['SenderEmail'],
                'year': received_time.year,
                'month': received_time.month,
                'day': received_time.day
            }
    return None

def display_email_metadata(metadata: Dict):
    """Display email metadata in a formatted table."""
    table = Table(title="Email Metadata")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Subject", metadata['subject'])
    table.add_row("Sender Name", metadata['sender_name'])
    table.add_row("Sender Email", metadata['sender_email'])
    table.add_row("Date", f"{metadata['year']}-{metadata['month']:02d}-{metadata['day']:02d}")
    
    console.print(table)

def display_analysis(analysis: QueryAnalysis):
    """Display query analysis results in a formatted table"""
    table = Table(title="Query Analysis Results")
    table.add_column("Component", style="cyan")
    table.add_column("Details", style="green")
    
    # Thought process
    if hasattr(analysis, 'thought_process'):
        thought_process = "\n".join(analysis.thought_process)
        table.add_row("Thought Process", thought_process)
    
    # Company info
    company_details = (
        f"Name: {analysis.company_info.name}\n"
        f"Origin: {analysis.company_info.origin}\n"
        f"Confidence: {analysis.company_info.confidence:.2f}\n"
        f"Variations: {', '.join(analysis.company_info.variations)}"
    )
    table.add_row("Company Info", company_details)
    
    # Temporal info
    temporal_details = (
        f"Years: {analysis.temporal_info.years}\n"
        f"Months: {analysis.temporal_info.months}\n"
        f"Quarter: {analysis.temporal_info.quarter}\n"
        f"Confidence: {analysis.temporal_info.confidence:.2f}"
    )
    table.add_row("Temporal Info", temporal_details)
    
    # Content info
    content_details = (
        f"Domain: {analysis.content_info.domain}\n"
        f"Key Terms: {', '.join(analysis.content_info.key_terms)}\n"
        f"Action Type: {analysis.content_info.action_type}\n"
        f"Confidence: {analysis.content_info.confidence:.2f}"
    )
    table.add_row("Content Info", content_details)
    
    console.print(table)

@app.command()
def run(query: str = typer.Argument(..., help="Query to analyze")):
    """Run analyzer on a query"""
    analyzer = QueryAnalyzer()
    analysis = analyzer.invoke(query)
    if analysis:
        display_analysis(analysis)
    else:
        console.print("[red]Failed to analyze query[/red]")

@app.command()
def prompt(query: str = typer.Argument(..., help="Query")):
    """View LLM prompt"""
    analyzer = QueryAnalyzer()
    prompt = analyzer.get_prompt({"query": query})
    console.print("\nPrompt:")
    console.print("-" * 80)
    console.print(prompt)

@app.command()
def test(
    idx: int = typer.Argument(0, help="Test case index"),
    prompt: bool = typer.Option(False, "--prompt", help="Show prompt"),
    expected: bool = typer.Option(False, "--expected", help="Show expected"),
    run: bool = typer.Option(False, "--run", help="Run analyzer"),
    metadata: bool = typer.Option(False, "--metadata", "-m", help="Show email metadata")
):
    """Test case from qa_pairs.json"""
    queries = load_test_queries()
    if idx >= len(queries):
        console.print(f"[red]Error: Index {idx} out of range. Only {len(queries)} test cases.[/red]")
        return
    
    test_case = queries[idx]
    query = test_case["Question"]
    
    console.rule(f"[bold]Test Case {idx}")
    console.print(f"Query: {query}")
    
    if metadata:
        console.print("\nEmail Metadata:")
        email_metadata = load_email_metadata(test_case["Conversation_ID"])
        if email_metadata:
            display_email_metadata(email_metadata)
        else:
            console.print("[red]No metadata found for this conversation[/red]")
    
    if expected:
        console.print("\nExpected Answer:")
        console.print(test_case["Answer"])
        console.print("\nExpected Thought Process:")
        for thought in test_case["Thought_Process"]:
            console.print(f"- {thought}")
    
    analyzer = QueryAnalyzer()
    
    if prompt:
        prompt_text = analyzer.get_prompt({"query": query})
        console.print("\nPrompt:")
        console.print("-" * 80)
        console.print(prompt_text)
    
    if run:
        console.print("\nAnalysis Results:")
        analysis = analyzer.invoke(query)
        if analysis:
            display_analysis(analysis)
        else:
            console.print("[red]Failed to analyze query[/red]")

@app.command()
def list():
    """List test cases"""
    queries = load_test_queries()
    
    table = Table(title="Test Cases")
    table.add_column("#", style="cyan")
    table.add_column("Query", style="green")
    table.add_column("ID", style="blue")
    
    for idx, test_case in enumerate(queries):
        table.add_row(
            str(idx),
            test_case["Question"],
            test_case["Conversation_ID"]
        )
    
    console.print(table)

@app.command()
def find(conversation_id: str = typer.Argument(..., help="Conversation ID to find")):
    """Find test case by conversation ID"""
    idx = find_test_case_index(conversation_id)
    if idx is not None:
        queries = load_test_queries()
        test_case = queries[idx]
        console.print(f"[green]Found test case at index: {idx}[/green]")
        console.print(f"Query: {test_case['Question']}")
    else:
        console.print(f"[red]No test case found with conversation ID: {conversation_id}[/red]")

if __name__ == "__main__":
    app()
