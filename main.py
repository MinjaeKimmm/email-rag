import typer
from pathlib import Path
from pipeline.filter.pipeline import run_filter
from pipeline.preprocess.pipeline import run_preprocess
from pipeline.eval.generate_qa_data import run_qa_generation
from pipeline.chunking.pipeline import EmailProcessingPipeline
from pipeline.eval.retriever_eval import eval_retriever_simple

app = typer.Typer()

@app.command()
def preprocess_emails(
    input_file: str = "email_conversations.json"
):
    """
    Preprocess emails from the input file, including body content and attachments.
    
    Args:
        input_file: Name of the input JSON file in the data directory (default: email_conversations.json)
    """
    print(f"Preprocessing emails from {input_file}...")
    run_preprocess(input_file=input_file)

@app.command()
def filter_emails(
    input_file: str = "preprocessed_email_conversations.json",
    output_dir: str = "processed_emails"
):
    """
    Process and classify emails from the preprocessed file.
    
    Args:
        input_file: Name of the input JSON file in the data directory (default: preprocessed_email_conversations.json)
        output_dir: Name of the output directory in the data directory (default: processed_emails)
    """
    print(f"Processing emails from {input_file}...")
    run_filter(input_file=input_file, output_dir=output_dir)

@app.command()
def generate_qa(
    input_file: str = "included_emails.json",
    output_file: str = "qa_pairs.json"
):
    """
    Generate QA pairs from processed emails.
    
    Args:
        input_file: Name of the input JSON file in the processed_emails directory (default: included_emails.json)
        output_file: Name of the output JSON file to store QA pairs (default: qa_pairs.json)
    """
    print(f"Generating QA pairs from {input_file}...")
    run_qa_generation(input_file=input_file, output_file=output_file)

@app.command()
def embed_emails(
    input_file: str = "included_emails.json"
):
    """
    Process emails into chunks and create embeddings.
    
    Args:
        input_file: Name of the input JSON file in the processed_emails directory (default: included_emails.json)
    """
    from pipeline.chunking.pipeline import run_embed
    run_embed(input_file=input_file)

@app.command()
def eval_retriever(
    retriever: str = "vector",  
    subset: str = None 
):
    """Evaluate retriever performance using NDCG.
    If no subset is specified, evaluates all questions.
    For subset, use format like '0:100' or '500:600'.
    """
    if subset:
        start, end = map(int, subset.split(':'))
    else:
        start, end = 0, None  
        
    eval_retriever_simple(retriever_type=retriever, start_idx=start, end_idx=end)

@app.command()
def query(
    query: str = typer.Argument(..., help="Query to search for in the email corpus"),
    retriever: str = typer.Option("weighted", help="Type of retriever to use (vector, bm25, weighted)"),
    max_tokens: int = typer.Option(10000, help="Maximum tokens in context"),
    top_k: int = typer.Option(15, help="Number of top chunks to retrieve")
):
    """Run a query through the RAG pipeline and get a response."""
    from pipeline.generation.pipeline import run_full_pipeline
    
    print(f"\nQuerying with: {query}")
    print(f"Using {retriever} retriever, max_tokens={max_tokens}, top_k={top_k}")
    
    response = run_full_pipeline(
        query=query,
        retriever_type=retriever,
        max_tokens=max_tokens,
        top_k=top_k
    )
    
    print("\nResponse:")
    print(response)

if __name__ == "__main__":
    app()
