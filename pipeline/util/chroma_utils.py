"""Utility functions for managing ChromaDB collections."""

import os
from typing import Dict, List
import chromadb
from rich import print
from rich.table import Table
from langchain_chroma import Chroma

from ..common.settings import get_embedding_dirname, EMBEDDINGS

def get_collection_details(dataset: str = "parent_child") -> Dict[str, Chroma]:
    """Get details of all collections in the embedding directory.
    
    Args:
        dataset: Name of the dataset to get collections for
        
    Returns:
        Dictionary mapping collection names to Chroma objects
    """
    embedding_dir = get_embedding_dirname(dataset)
    client = chromadb.PersistentClient(path=str(embedding_dir))
    collection_names = client.list_collections()
    
    collection_map = {}
    for name in collection_names:
        db = Chroma(
            client=client,
            collection_name=name,
            embedding_function=EMBEDDINGS
        )
        collection_map[name] = db
    return collection_map

def list_collections(dataset: str = "parent_child"):
    """List all collections and their details.
    
    Args:
        dataset: Name of the dataset to list collections for
    """
    embedding_dir = get_embedding_dirname(dataset)
    print(f"\n[bold]Collections in {embedding_dir}:[/bold]")
    
    table = Table(show_header=True, header_style="bold")
    table.add_column("Collection Name")
    table.add_column("Number of Documents")
    table.add_column("Directory")
    
    collection_map = get_collection_details(dataset)
    
    # Show collections and their details
    for name, db in collection_map.items():
        doc_count = db._collection.count()
        dir_path = os.path.join(embedding_dir, name)
        table.add_row(
            name,
            str(doc_count),
            dir_path if os.path.exists(dir_path) else "[red]Not found[/red]"
        )
    
    print(table)

def delete_collection(collection_name: str, dataset: str = "parent_child"):
    """Delete a collection.
    
    Args:
        collection_name: Name of collection to delete
        dataset: Name of the dataset the collection belongs to
    """
    try:
        embedding_dir = get_embedding_dirname(dataset)
        client = chromadb.PersistentClient(path=str(embedding_dir))
        client.delete_collection(collection_name)
        print(f"[green]Successfully deleted collection:[/green] {collection_name}")
    except Exception as e:
        print(f"[red]Error deleting collection:[/red] {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Manage ChromaDB collections")
    parser.add_argument("--dataset", default="parent_child", help="Dataset to manage collections for")
    parser.add_argument("--delete", help="Name of collection to delete")
    args = parser.parse_args()
    
    if args.delete:
        delete_collection(args.delete, args.dataset)
    else:
        list_collections(args.dataset)
