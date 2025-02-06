from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class BaseRetriever(ABC):
    """Base class for all retrievers"""
    
    @abstractmethod
    def retrieve(
        self,
        query: str,
        filter_dict: Optional[Dict] = None,
        k: int = 100
    ) -> List[Dict[str, Any]]:
        """Retrieve documents based on query
        
        Args:
            query: Query text
            filter_dict: Optional filter dictionary
            k: Number of results to return
            
        Returns:
            List of documents with scores and metadata
        """
        pass
