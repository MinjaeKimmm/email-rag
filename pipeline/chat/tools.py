"""Tools for the chat pipeline using Langchain's BaseTool."""
from typing import Dict, Any, Optional, List, Literal
import json
from langchain.tools import BaseTool
from pydantic import Field

from ..retrieval.analyzer import QueryAnalyzer
from ..retrieval.filter_builder import ElasticsearchFilterBuilder
from ..retrieval.retrievers import VectorRetriever, WeightedAverageRetriever
from ..retrieval.processor import ConversationProcessor
from ..retrieval.schema import RetrievalResult
from ..generation.context_builder import ContextBuilder
from ..generation.generator import Generator
from ..common.store import EmailStore

RetrieverType = Literal["basic", "advanced"]

class QueryAnalysisTool(BaseTool):
    """Tool for analyzing queries and building Elasticsearch filters."""
    
    name: str = Field(default="query_analyzer")
    description: str = Field(default="Analyzes queries and builds Elasticsearch filters")
    analyzer: Optional[QueryAnalyzer] = Field(default=None)
    filter_builder: Optional[ElasticsearchFilterBuilder] = Field(default=None)
    
    def __init__(self, **kwargs):
        """Initialize the query analysis tool."""
        super().__init__(**kwargs)
        self.analyzer = QueryAnalyzer()
        self.filter_builder = ElasticsearchFilterBuilder()
    
    def _run(self, query: str) -> Dict[str, Any]:
        """Run query analysis.
        
        Args:
            query: Query string to analyze
            
        Returns:
            Dict containing query and optional analysis/filter
        """
        try:
            analysis = self.analyzer.invoke(query)
            result = {"query": query}
            if analysis:
                # Convert Pydantic model to dict for JSON serialization
                result["analysis"] = analysis.model_dump() if hasattr(analysis, 'model_dump') else analysis
                result["filter_dict"] = self.filter_builder.build_filter(analysis)
            return result
        except Exception as e:
            return {"query": query, "error": str(e)}

class ContentRetrievalTool(BaseTool):
    """Tool for retrieving relevant content using vector or weighted retrieval."""
    
    name: str = Field(default="content_retriever")
    description: str = Field(default="Retrieves relevant content using vector or weighted retrieval")
    store: Optional[EmailStore] = Field(default=None)
    retriever_type: str = Field(default="advanced")
    k: int = Field(default=100)
    
    def __init__(self, **kwargs):
        """Initialize the content retrieval tool."""
        super().__init__(**kwargs)
        self.store = EmailStore()
    
    def _run(
        self,
        query: str
    ) -> Dict[str, Any]:
        """Run content retrieval.
        
        Args:
            query: Query string to search for
                
        Returns:
            Dict containing query and retrieval results
        """
        # Build query info using QueryAnalyzer if needed
        if self.retriever_type == "advanced":
            query_info = QueryAnalysisTool().run(query)
        else:
            query_info = {"query": query}
        
        if self.retriever_type == "basic":
            retriever = VectorRetriever(store=self.store)
            results = retriever.retrieve(query=query_info["query"], k=self.k)
        else:
            retriever = WeightedAverageRetriever(store=self.store)
            results = retriever.retrieve(
                query=query_info["query"],
                analysis=query_info.get("analysis"),
                filter_dict=query_info.get("filter_dict"),
                k=self.k
            )
        
        return {
            "query": query_info["query"],
            "results": results
        }

class ResultProcessorTool(BaseTool):
    """Tool for processing and grouping retrieval results."""
    
    name: str = Field(default="result_processor")
    description: str = Field(default="Processes and groups retrieval results")
    processor: Optional[ConversationProcessor] = Field(default=None)
    return_conversations: bool = Field(default=True)
    top_k: int = Field(default=15)
    
    def __init__(self, **kwargs):
        """Initialize the result processor tool."""
        super().__init__(**kwargs)
        self.processor = ConversationProcessor()
    
    def _run(
        self,
        retrieval_output_str: str
    ) -> RetrievalResult:
        """Process retrieval results.
        
        Args:
            retrieval_output_str: JSON string of retrieval output
                
        Returns:
            RetrievalResult object
        """
        # Parse retrieval output from JSON string
        retrieval_output = json.loads(retrieval_output_str)
        
        conversation_groups = self.processor.group_conversations(
            retrieval_output["results"]
        )
        
        result = RetrievalResult(query=retrieval_output["query"])
        result.conversation_groups = conversation_groups
        
        if self.return_conversations:
            result.top_conversations = self.processor.select_top_conversations(
                conversation_groups
            )[:self.top_k]
        else:
            all_chunks = []
            for group in conversation_groups.values():
                all_chunks.extend(group.chunks)
            result.top_chunks = sorted(
                all_chunks,
                key=lambda x: x.get("combined_score", x.get("vector_score", 0)),
                reverse=True
            )[:self.top_k]
        
        return result

class ResponseGeneratorTool(BaseTool):
    """Tool for generating responses using retrieved context."""
    
    name: str = Field(default="response_generator")
    description: str = Field(default="Generates responses using retrieved context")
    context_builder: Optional[ContextBuilder] = Field(default=None)
    generator: Optional[Generator] = Field(default=None)
    max_tokens: int = Field(default=10000)
    
    def __init__(self, **kwargs):
        """Initialize the response generator tool."""
        super().__init__(**kwargs)
        self.context_builder = ContextBuilder(max_tokens=self.max_tokens)
        self.generator = Generator()
    
    def _run(
        self,
        input_str: str
    ) -> Dict[str, Any]:
        """Generate response using retrieved context.
        
        Args:
            input_str: JSON string containing query and retrieval result
                
        Returns:
            Dict containing response, thought process, and used chunks
        """
        # Parse input from JSON string
        input_data = json.loads(input_str)
        query = input_data["query"]
        retrieval_result = RetrievalResult(**input_data["retrieval_result"])
        
        context = self.context_builder.build(retrieval_result)
        
        llm_response = self.generator.invoke({
            "query": query,
            "context": context
        })
        
        if not llm_response:
            return {
                "error": "Failed to generate valid response",
                "thought_process": [],
                "response": "",
                "used_chunks": []
            }
        
        used_chunks = []
        for chunk_id, reason in llm_response["answer"].items():
            chunk = self._get_chunk_content(retrieval_result, chunk_id)
            if chunk:
                used_chunks.append({
                    "chunk_id": chunk_id,
                    "reason": reason,
                    "content": chunk["text"],
                    "metadata": chunk["metadata"]
                })
        
        return {
            "thought_process": llm_response["thought_process"],
            "response": llm_response["response"],
            "used_chunks": used_chunks
        }
    
    def _get_chunk_content(
        self,
        result: RetrievalResult,
        chunk_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get chunk content by ID."""
        try:
            chunk_idx = int(chunk_id)
            for conv in result.conversation_groups.values():
                for chunk in conv.get('chunks', []):
                    if chunk['metadata'].get('chunk_index') == chunk_idx:
                        return chunk
        except ValueError:
            return None
        return None

def run_tools_pipeline(
    query: str,
    retriever_type: RetrieverType = "advanced",
    return_conversations: bool = True,
    top_k: int = 15,
    max_tokens: int = 10000
) -> Dict[str, Any]:
    """Run the complete pipeline using Langchain tools.
    
    Args:
        query: User query string
        retriever_type: Type of retriever to use
        return_conversations: Whether to return conversations
        top_k: Number of top results to return
        max_tokens: Max tokens for context building
        
    Returns:
        Dictionary containing final response and metadata
    """
    # Initialize tools with configuration
    content_retriever = ContentRetrievalTool(retriever_type=retriever_type)
    result_processor = ResultProcessorTool(
        return_conversations=return_conversations,
        top_k=top_k
    )
    response_generator = ResponseGeneratorTool(max_tokens=max_tokens)
    
    # Run pipeline steps
    # 1. Retrieve content (includes analysis if needed)
    retrieval_output = content_retriever.run(query)
    
    # 2. Process results
    retrieval_result = result_processor.run(
        json.dumps(retrieval_output)
    )
    
    # 3. Generate response
    final_output = response_generator.run(
        json.dumps({
            "query": query,
            "retrieval_result": retrieval_result.model_dump()
        })
    )
    
    return final_output

if __name__ == "__main__":
    print(run_tools_pipeline("Summarize the reports on Samsung SDS over the past 3 quarter"))