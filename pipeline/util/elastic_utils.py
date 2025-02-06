"""Utility functions for managing Elasticsearch indices."""

import os
from typing import Dict, List
from elasticsearch import Elasticsearch
from rich import print
from rich.table import Table
from langchain_elasticsearch import ElasticsearchStore

from ..common.settings import ELASTIC_URL, ELASTIC_USER, ELASTIC_PASSWORD, EMBEDDINGS

def get_index_details() -> Dict[str, ElasticsearchStore]:
    """Get details of all email indices in Elasticsearch.
    
    Returns:
        Dictionary mapping index names to ElasticsearchStore objects
    """
    client = Elasticsearch(
        ELASTIC_URL,
        basic_auth=(ELASTIC_USER, ELASTIC_PASSWORD)
    )
    
    # Get all indices
    indices = client.indices.get(index='*')
    
    # Filter for our email indices (exclude status indices)
    email_indices = {name: info for name, info in indices.items() 
                    if not name.endswith('_status')}
    
    # Create ElasticsearchStore objects for each index
    index_map = {}
    for name in email_indices:
        store = ElasticsearchStore(
            es_url=ELASTIC_URL,
            es_user=ELASTIC_USER,
            es_password=ELASTIC_PASSWORD,
            index_name=name,
            embedding=EMBEDDINGS
        )
        index_map[name] = store
    return index_map

def list_indices():
    """List all indices and their details."""
    client = Elasticsearch(
        ELASTIC_URL,
        basic_auth=(ELASTIC_USER, ELASTIC_PASSWORD)
    )
    
    print("\n[bold]Elasticsearch Indices:[/bold]")
    
    table = Table(show_header=True, header_style="bold")
    table.add_column("Index Name")
    table.add_column("Number of Documents")
    table.add_column("Size")
    table.add_column("Status")
    
    # Get all indices
    indices = client.indices.get(index='*')
    stats = client.indices.stats(index='*')
    
    # Show indices and their details
    for name, info in indices.items():
        if name.endswith('_status'):
            continue  # Skip status indices
            
        doc_count = stats['indices'][name]['total']['docs']['count']
        size = stats['indices'][name]['total']['store']['size_in_bytes']
        size_str = f"{size / 1024 / 1024:.2f} MB"
        status = info['settings']['index']['creation_date']
        
        table.add_row(
            name,
            str(doc_count),
            size_str,
            "[green]Active[/green]" if info['settings']['index']['version']['created'] else "[red]Inactive[/red]"
        )
    
    print(table)

def delete_index(index_name: str):
    """Delete an index.
    
    Args:
        index_name: Name of index to delete
    """
    try:
        client = Elasticsearch(
            ELASTIC_URL,
            basic_auth=(ELASTIC_USER, ELASTIC_PASSWORD)
        )
        
        # Delete both the main index and its status index
        client.indices.delete(index=index_name)
        if client.indices.exists(index=f"{index_name}_status"):
            client.indices.delete(index=f"{index_name}_status")
            
        print(f"[green]Successfully deleted index:[/green] {index_name}")
    except Exception as e:
        print(f"[red]Error deleting index:[/red] {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Manage Elasticsearch indices")
    parser.add_argument("--delete", help="Name of index to delete")
    args = parser.parse_args()
    
    if args.delete:
        delete_index(args.delete)
    else:
        list_indices()
