from typing import List, Dict, Any, TypeVar, Sequence
from tqdm import tqdm
from ..common.store import EmailStore
from ..common.settings import ELASTIC_DEFAULT_INDEX
from .base import Chunk


T = TypeVar('T')
class EmailEmbedder:
    def __init__(self, index_name: str = ELASTIC_DEFAULT_INDEX, dataset: str = "email"):
        """Initialize the embedder with Elasticsearch
        
        Args:
            index_name: Name of the Elasticsearch index to use
            dataset: Name of the dataset (strategy) to use
        """
        self.index_name = index_name
        self.dataset = dataset
        self.store = EmailStore(index_name=index_name)

    def _get_embedding_status(self) -> str:
        """Get the current embedding status"""
        return self.store.get_embedding_status()
    
    def _set_embedding_status(self, status: str):
        """Set the embedding status"""
        self.store.set_embedding_status(status)
    
    def _clear_index(self):
        """Clear the index and reset status"""
        self.store.clear_index()
    
    def _process_chunks(self, chunks: List[Chunk], batch_size: int):
        """Process chunks in batches"""
        # Prepare data for embedding
        documents = []
        metadatas = []
        for chunk in chunks:
            if not chunk.content.strip():  # Skip empty chunks
                continue
            documents.append(chunk.content)
            metadatas.append(chunk.metadata.to_dict())

        if not documents:
            print("Error: No valid documents to embed")
            return

        print(f'Embedding {len(documents)} chunks')
        
        # Process in batches
        for i in tqdm(range(0, len(documents), batch_size)):
            batch_end = min(i + batch_size, len(documents))
            batch_documents = documents[i:batch_end]
            batch_metadatas = metadatas[i:batch_end]
            
            # Add to Elasticsearch - it will handle embeddings internally
            self.store.add_documents(
                texts=batch_documents,
                metadatas=batch_metadatas
            )
    
    def embed_chunks(self, chunks: List[Chunk], batch_size: int = 500):
        """Embed chunks in batches with status tracking"""
        print("=== Checking Embedding Status ===")
        doc_count = self.store.client.count(index=self.index_name)['count']
        status = self._get_embedding_status()
        print(f"Index: {self.index_name}")
        print(f"Status: {status}")
        print(f"Documents: {doc_count}")
        
        if doc_count > 0:
            if status == "COMPLETE":
                print("\nEmbeddings are complete, no need to reprocess")
                return
            else:
                print("\nFound documents but status is not complete")
                print("Clearing index to start fresh...")
                self._clear_index()
        else:
            print("\nNo existing documents found")
            print("Initializing fresh embedding process...")
            self._clear_index()

        # Start embedding process
        self._set_embedding_status("IN_PROGRESS")
        try:
            self._process_chunks(chunks, batch_size)
            self._set_embedding_status("COMPLETE")
            print("Embedding process completed successfully")
        except Exception as e:
            self._set_embedding_status("FAILED")
            print(f"Embedding process failed: {str(e)}")
            raise e

    def remove_small_chunks(self, min_length: int = 30):
        """Remove chunks that are too small
        
        Args:
            min_length: Minimum length of chunks to keep (in characters)
        """
        print(f'Removing chunks smaller than {min_length} characters...')
        
        try:
            # Delete documents where text length is less than min_length
            response = self.store.client.delete_by_query(
                index=self.store.index_name,
                body={
                    "query": {
                        "bool": {
                            "must": [
                                {
                                    "script": {
                                        "script": {
                                            "source": "doc['_source']['text'].length() < params.min_length",
                                            "lang": "painless",
                                            "params": {
                                                "min_length": min_length
                                            }
                                        }
                                    }
                                }
                            ]
                        }
                    }
                },
                refresh=True
            )
            
            deleted_count = response.get('deleted', 0)
            print(f'Removed {deleted_count} small chunks')
            
        except Exception as e:
            print(f"Error removing small chunks: {e}")
