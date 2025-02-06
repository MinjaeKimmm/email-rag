from typing import List, Dict, Any
from .config import RetrievalConfig
from .analyzer.query_analyzer import QueryAnalyzer
from .store.filter_builder import ChromaFilterBuilder
from .store.chroma_store import ChromaStore
from .scoring.scorer import RelevanceScorer
from .processor.conversation import ConversationProcessor
from pipeline.common.settings import LLM

class EnhancedRetriever:
    def __init__(self, config: RetrievalConfig = None):
        self.config = config or RetrievalConfig()
        
        # Initialize components
        self.analyzer = QueryAnalyzer()
        
        self.store = ChromaStore(
            collection_name=self.config.collection_name,
            persist_directory=self.config.persist_directory
        )
        
        self.filter_builder = ChromaFilterBuilder()
        self.scorer = RelevanceScorer(weights=self.config.scoring_weights)
        self.processor = ConversationProcessor(
            max_chunk_length=self.config.max_chunk_length
        )

    def get_relevant_documents(self, query: str) -> List[Dict]:
        """Main retrieval pipeline"""
        # 1. Analyze query
        analysis = self.analyzer.invoke(query)
        
        # 2. Build filter
        filter_dict = self.filter_builder.build_filter(analysis)
        
        # 3. Initial retrieval
        initial_results = self.store.search(
            query=query,
            filter_dict=filter_dict,
            k=100  # Get more initially for scoring
        )
        
        # 4. Score conversations
        conversation_scores = {}
        current_conversation = []
        current_conv_id = None
        
        # Group by conversation and score
        for chunk in initial_results:
            conv_id = chunk['metadata']['conversation_id']
            
            if conv_id != current_conv_id:
                if current_conversation:
                    # Score previous conversation
                    conversation_scores[current_conv_id] = self.scorer.score_conversation(
                        current_conversation,
                        analysis
                    )
                current_conversation = []
                current_conv_id = conv_id
            
            current_conversation.append(chunk)
        
        # Score last conversation
        if current_conversation:
            conversation_scores[current_conv_id] = self.scorer.score_conversation(
                current_conversation,
                analysis
            )
        
        # 5. Group conversations
        conversation_groups = self.processor.group_conversations(
            initial_results,
            conversation_scores
        )
        
        # 6. Select and process top conversations
        final_results = self.processor.select_top_conversations(
            conversation_groups,
            max_conversations=self.config.max_conversations
        )
        
        return final_results
