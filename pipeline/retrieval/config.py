from dataclasses import dataclass, field
from typing import Dict
from pipeline.common.settings import LLM_MODEL, ELASTIC_DEFAULT_INDEX

@dataclass
class RetrievalConfig:
    # General settings
    max_conversations: int = 5
    max_chunk_length: int = 1000
    
    # Scoring weights
    scoring_weights: Dict[str, float] = field(default_factory=lambda: {
        "vector": 0.6,
        "company": 0.2,
        "temporal": 0.2
    })
    
    # Confidence thresholds
    min_company_confidence: float = 0.5
    min_temporal_confidence: float = 0.5
    
    # Relevance thresholds
    high_relevance_threshold: float = 0.7
    
    # Model settings - using common settings
    llm_model: str = LLM_MODEL  # From common settings
    
    # Elasticsearch settings
    index_name: str = ELASTIC_DEFAULT_INDEX
