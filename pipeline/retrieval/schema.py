from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class QuarterInfo(BaseModel):
    number: Optional[List[int]] = Field(None)
    year: Optional[List[int]] = None
    
    @property
    def is_complete(self) -> bool:
        """Check if both number and year lists are present and of same length."""
        if self.number is None or self.year is None:
            return False
        return len(self.number) == len(self.year) and len(self.number) > 0

    def __init__(self, **data):
        super().__init__(**data)
        if self.number is not None:
            # Validate quarter numbers
            if not all(1 <= q <= 4 for q in self.number):
                raise ValueError("Quarter numbers must be between 1 and 4")
        
        # Check if one is None while other isn't
        if (self.number is None) != (self.year is None):
            raise ValueError("Both number and year must be either present or absent")

class CompanyInfo(BaseModel):
    name: Optional[str] = None
    origin: Optional[str] = None
    variations: Optional[List[str]] = None
    confidence: float = Field(0, ge=0, le=1)

class TemporalInfo(BaseModel):
    years: Optional[List[int]] = None
    months: Optional[List[int]] = None
    quarter: Optional[QuarterInfo] = None
    confidence: float = Field(0, ge=0, le=1)

class ContentInfo(BaseModel):
    """Information about the content/topic-specific terms in the query."""
    domain: Optional[str] = Field(None, description="High-level domain of the query (e.g., 'gaming', 'semiconductors', 'automotive')")
    key_terms: Optional[List[str]] = Field(None, description="Important domain-specific terms (e.g., 'SSD controllers', 'game releases')")
    action_type: Optional[str] = Field(None, description="Type of action/event (e.g., 'announcement', 'contract', 'earnings')")
    confidence: float = Field(0, ge=0, le=1)

class QueryAnalysis(BaseModel):
    thought_process: List[str]
    company_info: CompanyInfo
    temporal_info: TemporalInfo
    content_info: ContentInfo
    original_query: str


class RetrievalResult(BaseModel):
    """Result from the retrieval pipeline"""
    query: str
    analysis: Optional[QueryAnalysis] = None  # Query analysis if available
    filter_dict: Optional[Dict] = None  # Elasticsearch filter if available
    conversation_groups: Dict[str, Any] = Field(default_factory=dict)  # All conversation groups
    top_conversations: Optional[List[Dict]] = None  # Top N conversations with their chunks
    top_chunks: Optional[List[Dict]] = None  # Top N chunks across all conversations
