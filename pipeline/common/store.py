from typing import List, Dict, Any, Optional
from datetime import datetime
from elasticsearch import Elasticsearch
from langchain_elasticsearch import ElasticsearchStore
from .settings import ELASTIC_URL, ELASTIC_USER, ELASTIC_PASSWORD, EMBEDDINGS

class EmailStore:
    """Unified store for both embedding storage and retrieval using Elasticsearch"""
    
    def __init__(self, index_name: str = "emails", status_index: str = "email_status"):
        """Initialize the Elasticsearch store
        
        Args:
            index_name: Name of the Elasticsearch index to use
            status_index: Name of the index for storing embedding status
        """
        # Initialize Elasticsearch client
        self.index_name = index_name
        self.status_index = status_index
        
        # Define our index mapping
        self.es_mapping = {
            "mappings": {
                "properties": {
                    "text": {"type": "text"},  # The actual content
                    "metadata": {
                        "properties": {
                            # Email-specific metadata
                            "conversation_id": {"type": "keyword"},
                            "subject": {"type": "text"},
                            "sender_name": {"type": "text"},
                            "sender_email": {"type": "text"},
                            "year": {"type": "integer"},
                            "month": {"type": "integer"},
                            "day": {"type": "integer"},
                            
                            # Chunk-specific metadata
                            "chunk_type": {"type": "keyword"},  # email_body or attachment
                            "chunk_index": {"type": "integer"},
                            "total_chunks": {"type": "integer"},
                            
                            # Attachment metadata (optional)
                            "attachment_metadata": {
                                "type": "object",
                                "enabled": True  # Allow dynamic fields
                            }
                        }
                    },
                    "embedding": {"type": "dense_vector"}
                }
            }
        }
        
        # Initialize Elasticsearch client
        self.client = Elasticsearch(
            ELASTIC_URL,
            basic_auth=(ELASTIC_USER, ELASTIC_PASSWORD)
        )
        
        # Create status index if it doesn't exist
        if not self.client.indices.exists(index=status_index):
            self.client.indices.create(
                index=status_index,
                mappings={
                    "properties": {
                        "status": {"type": "keyword"},
                        "timestamp": {"type": "date"}
                    }
                }
            )
        
        # Create main index with our mapping if it doesn't exist
        if not self.client.indices.exists(index=index_name):
            self.client.indices.create(
                index=index_name,
                body=self.es_mapping
            )
        
        # Initialize store with search configuration
        self.store = ElasticsearchStore(
            es_url=ELASTIC_URL,
            es_user=ELASTIC_USER,
            es_password=ELASTIC_PASSWORD,
            index_name=index_name,
            embedding=EMBEDDINGS
        )
    
    def add_documents(self, texts: List[str], metadatas: List[Dict[str, Any]]) -> List[str]:
        """Add documents with their metadata to the store
        
        Args:
            texts: List of document texts
            metadatas: List of metadata dictionaries
            
        Returns:
            List of document IDs
        """
        ids = self.store.add_documents(texts=texts, metadatas=metadatas)
        # Force refresh the index to make documents searchable immediately
        self.client.indices.refresh(index=self.index_name)
        return ids
    
    def similarity_search(
        self,
        query: str,
        filter_dict: Optional[Dict] = None,
        k: int = 50
    ) -> List[Dict]:
        """Search for similar documents with optional filters
        
        Args:
            query: Query text
            filter_dict: Optional Elasticsearch filter query
            k: Number of results to return (default: 50)
            
        Returns:
            List of documents with their metadata and scores
        """
        # Get query embedding
        embedding = EMBEDDINGS.embed_query(query)
        
        # Build search query
        knn = {
            "field": "vector",
            "query_vector": embedding,
            "k": k,
            "num_candidates": max(k * 2, 100)
        }
        
        # Add filter if provided
        if filter_dict:
            search_query = {
                "query": {
                    "bool": {
                        "filter": filter_dict,
                        "must": {
                            "knn": knn
                        }
                    }
                }
            }
        else:
            search_query = {
                "query": {
                    "knn": knn
                }
            }
        
        # Execute search
        response = self.client.search(
            index=self.index_name,
            body=search_query,
            size=k
        )
        
        # Process results
        results = []
        for hit in response["hits"]["hits"]:
            doc = hit["_source"]
            doc["vector_score"] = hit["_score"]
            doc["combined_score"] = hit["_score"]
            
            # Extract boost information
            if "matched_queries" in hit:
                doc["boosts"] = hit["matched_queries"]
            
            results.append(doc)
        
        return results
    
    def get_embedding_status(self) -> str:
        """Get the current embedding status"""
        try:
            # Force refresh to get latest status
            self.client.indices.refresh(index=self.status_index)
            result = self.client.get(
                index=self.status_index,
                id="embedding_status"
            )
            return result["_source"]["status"]
        except Exception as e:
            print(f"Status check error (returning NOT_STARTED): {e}")
            return "NOT_STARTED"
    
    def set_embedding_status(self, status: str):
        """Set the embedding status"""
        try:
            # Set status
            self.client.index(
                index=self.status_index,
                id="embedding_status",
                document={
                    "status": status,
                    "timestamp": datetime.utcnow()
                },
                refresh=True  # Force refresh
            )
            print(f"Status set to: {status}")
        except Exception as e:
            print(f"Error setting status: {e}")
    
    def clear_index(self):
        """Clear the main index and reset status"""
        print("Clearing existing index...")
        try:
            # Delete and recreate the index
            if self.client.indices.exists(index=self.index_name):
                self.client.indices.delete(index=self.index_name)
            
            # Store will recreate the index with proper mapping
            self.store = ElasticsearchStore(
                es_url=ELASTIC_URL,
                es_user=ELASTIC_USER,
                es_password=ELASTIC_PASSWORD,
                index_name=self.index_name,
                embedding=EMBEDDINGS
            )
            self.set_embedding_status("NOT_STARTED")
        except Exception as e:
            print(f"Error clearing index: {e}")
    
    def add_documents(self, texts: List[str], metadatas: List[Dict[str, Any]]):
        """Add documents to the store with their metadata
        
        Args:
            texts: List of document texts
            metadatas: List of metadata dictionaries
        """
        if len(texts) != len(metadatas):
            raise ValueError("Number of texts must match number of metadata dicts")
        
        # Add documents in a single batch
        self.store.add_texts(
            texts=texts,
            metadatas=metadatas
        )
        
    def count_documents(self) -> int:
        """Get the total number of documents in the index"""
        try:
            result = self.client.count(index=self.index_name)
            return result["count"]
        except Exception as e:
            print(f"Error counting documents: {e}")
            return 0
            
    def get_chunks_by_conversation_id(self, conversation_id: str) -> List[Dict]:
        """Get all chunks for a conversation ID"""
        # Build Elasticsearch query to get all chunks from a conversation
        query = {
            "query": {
                "match": {
                    "metadata.conversation_id.keyword": conversation_id
                }
            },
            "size": 100,  # Should be enough for any conversation
            "sort": [
                {"metadata.chunk_index": "asc"}  # Sort by chunk index
            ]
        }
        
        try:
            # Execute search
            response = self.client.search(
                index=self.index_name,
                body=query
            )
            
            # Convert hits to chunks
            chunks = []
            for hit in response['hits']['hits']:
                source = hit['_source']
                chunk = {
                    'text': source['text'],
                    'metadata': source['metadata'],
                    'vector_score': 0,  # No vector score since this is direct fetch
                    'combined_score': 0  # No score since this is direct fetch
                }
                chunks.append(chunk)
                
            if not chunks:
                print(f"Warning: No chunks found for conversation {conversation_id}")
                
            return chunks
        except Exception as e:
            print(f"Error fetching chunks for conversation {conversation_id}: {e}")
            return []
