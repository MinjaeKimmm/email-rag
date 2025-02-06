from typing import List, Dict, Any, Optional
from pydantic import Field
from langchain.schema.runnable import RunnablePassthrough
from langchain.schema import BaseRetriever as LangchainBaseRetriever
from .base_retriever import BaseRetriever
from ..common.store import EmailStore
from .filter_builder import ElasticsearchFilterBuilder

class VectorRetriever(BaseRetriever, LangchainBaseRetriever):
    """Pure vector similarity-based retriever"""
    
    store: EmailStore = Field(description="Email store for vector search")
        
    def get_relevant_documents(self, query: str) -> List[Dict[str, Any]]:
        return self.retrieve(query)
    
    def retrieve(
        self,
        query: str,
        filter_dict: Optional[Dict] = None,
        k: int = 100
    ) -> List[Dict[str, Any]]:
        # Ignore filter_dict, only use vector similarity
        results = self.store.similarity_search(query=query, k=k)
        for result in results:
            result["combined_score"] = result["vector_score"]
        return results

class WeightedAverageRetriever(BaseRetriever, LangchainBaseRetriever):
    """Combines vector similarity and metadata using weighted average"""
    
    store: EmailStore = Field(description="Email store for vector search")
    vector_weight: float = Field(default=0.7, description="Weight for vector similarity score")
    metadata_weight: float = Field(default=0.3, description="Weight for metadata match score")
        
    def get_relevant_documents(self, query: str) -> List[Dict[str, Any]]:
        return self.retrieve(query)
    
    def retrieve(
        self,
        query: str,
        analysis: Optional[Any] = None,
        filter_dict: Optional[Dict] = None,
        k: int = 100
    ) -> List[Dict[str, Any]]:
        if not analysis:
            results = self.store.similarity_search(query=query, k=k)
            for result in results:
                result["combined_score"] = result["vector_score"]
            return results
            
        results = self.store.similarity_search(query=query, filter_dict=filter_dict, k=k)
        
        # Calculate weighted average scores
        for result in results:
            vector_score = result["vector_score"]
            metadata_matches = len(result.get("boosts", []))
            metadata_score = metadata_matches / 3.0  # Normalize by max possible matches
            
            result["combined_score"] = (
                (self.vector_weight * vector_score + self.metadata_weight * metadata_score) /
                (self.vector_weight + self.metadata_weight)
            )
            
        return sorted(results, key=lambda x: x["combined_score"], reverse=True)

class MultiplicativeRetriever(BaseRetriever, LangchainBaseRetriever):
    """Combines vector similarity and metadata using multiplication"""
    
    store: EmailStore = Field(description="Email store for vector search")
        
    def get_relevant_documents(self, query: str) -> List[Dict[str, Any]]:
        return self.retrieve(query)
    
    def retrieve(
        self,
        query: str,
        analysis: Optional[Any] = None,
        filter_dict: Optional[Dict] = None,
        k: int = 100
    ) -> List[Dict[str, Any]]:
        if not analysis:
            results = self.store.similarity_search(query=query, k=k)
            for result in results:
                result["combined_score"] = result["vector_score"]
            return results
            
        results = self.store.similarity_search(query=query, filter_dict=filter_dict, k=k)
        
        # Calculate multiplicative scores
        for result in results:
            vector_score = result["vector_score"]
            metadata_matches = len(result.get("boosts", []))
            metadata_score = metadata_matches / 3.0  # Normalize by max possible matches
            
            # Multiplicative scoring: vector_score * (1 + metadata_score)
            result["combined_score"] = vector_score * (1 + metadata_score)
            
        return sorted(results, key=lambda x: x["combined_score"], reverse=True)
