from typing import Dict, List, Literal
from langchain.schema.runnable import RunnablePassthrough

from ..common.store import EmailStore
from .retrievers import VectorRetriever, WeightedAverageRetriever, MultiplicativeRetriever
from .analyzer import QueryAnalyzer
from .filter_builder import ElasticsearchFilterBuilder
from .processor import ConversationProcessor, ConversationGroup
from .schema import RetrievalResult

# Type for retriever selection
RetrieverType = Literal["vector", "weighted", "multiplicative"]

class RetrievalPipeline:
    """Pipeline for retrieving and processing email conversations"""
    
    def __init__(self):
        """Initialize pipeline components"""
        self.store = EmailStore()
        
        # Initialize retrievers
        self.vector_retriever = VectorRetriever(store=self.store)
        self.weighted_retriever = WeightedAverageRetriever(store=self.store)
        self.multiplicative_retriever = MultiplicativeRetriever(store=self.store)
        
        # Initialize analyzer and filter builder
        self.query_analyzer = QueryAnalyzer()
        self.filter_builder = ElasticsearchFilterBuilder()
        
        # Initialize processor
        self.processor = ConversationProcessor()
        
        # Create retriever chains
        self._setup_chains()
    
    def _setup_chains(self):
        """Set up retriever chains"""
        # Vector-only chain (no query analysis)
        self.vector_chain = RunnablePassthrough() | {"results": lambda x: self.vector_retriever.retrieve(x)}
        
        # Weighted chain with query analysis
        self.weighted_chain = (
            RunnablePassthrough()
            | {"query": lambda x: x}
            | {
                "query": lambda x: x["query"],
                "analysis": lambda x: self.query_analyzer.invoke(x["query"]),
                "filter_dict": lambda x: self.filter_builder.build_filter(
                    self.query_analyzer.invoke(x["query"])
                ) if self.query_analyzer.invoke(x["query"]) else None
            }
            | {"results": lambda x: self.weighted_retriever.retrieve(
                query=x["query"],
                analysis=x["analysis"],
                filter_dict=x["filter_dict"]
              )}
        )
        
        # Multiplicative chain with query analysis
        self.multiplicative_chain = (
            RunnablePassthrough()
            | {"query": lambda x: x}
            | {
                "query": lambda x: x["query"],
                "analysis": lambda x: self.query_analyzer.invoke(x["query"]),
                "filter_dict": lambda x: self.filter_builder.build_filter(
                    self.query_analyzer.invoke(x["query"])
                ) if self.query_analyzer.invoke(x["query"]) else None
            }
            | {"results": lambda x: self.multiplicative_retriever.retrieve(
                query=x["query"],
                analysis=x["analysis"],
                filter_dict=x["filter_dict"]
              )}
        )
    
    def retrieve(
        self,
        query: str,
        retriever_type: RetrieverType = "multiplicative",
        return_conversations: bool = True,
        top_k: int = 5
    ) -> RetrievalResult:
        """Run the retrieval pipeline
        
        Args:
            query: Search query
            retriever_type: Type of retriever to use ("vector", "weighted", "multiplicative")
            return_conversations: If True, return conversation groups. If False, return individual chunks.
            top_k: Number of top results to return
            
        Returns:
            RetrievalResult containing query analysis and either conversation groups or chunks
        """
        # Initialize result
        result = RetrievalResult(query=query)
        
        # Run query analysis for weighted/multiplicative retrievers
        if retriever_type != "vector":
            try:
                result.analysis = self.query_analyzer.invoke(query)
                if result.analysis:
                    result.filter_dict = self.filter_builder.build_filter(result.analysis)
            except Exception as e:
                print(f"Warning: Query analysis failed: {e}")
                # Fall back to vector-only search if analysis fails
                result.analysis = None
                result.filter_dict = None
        
        # Select and run appropriate chain
        chain = {
            "vector": self.vector_chain,
            "weighted": self.weighted_chain,
            "multiplicative": self.multiplicative_chain
        }[retriever_type]
        
        output = chain.invoke(query)
        
        # Process results
        conversation_groups = self.processor.group_conversations(output["results"])
        result.conversation_groups = conversation_groups
        
        if return_conversations:
            # Return top conversations with their chunks
            result.top_conversations = self.processor.select_top_conversations(conversation_groups)
            # Limit to top_k if specified
            if top_k:
                result.top_conversations = result.top_conversations[:top_k]
        else:
            # Return top individual chunks
            all_chunks = []
            for group in conversation_groups.values():
                all_chunks.extend(group.chunks)
            result.top_chunks = sorted(
                all_chunks,
                key=lambda x: x.get("combined_score", x.get("vector_score", 0)),
                reverse=True
            )[:top_k] if top_k else all_chunks
        
        return result
