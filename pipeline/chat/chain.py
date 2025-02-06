"""Chain implementation for the analysis pipeline."""
from typing import Dict, List, Optional, Any, Union, Literal
import json
from uuid import UUID, uuid4
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.base_language import BaseLanguageModel

from pipeline.chat.tools import (
    QueryAnalysisTool,
    ContentRetrievalTool,
    ResultProcessorTool,
    ResponseGeneratorTool
)

RetrieverType = Literal["basic", "advanced"]

class AnalysisChain:
    """Chain that combines query analysis, content retrieval, and response generation."""
    
    def __init__(
        self,
        llm: BaseLanguageModel,
        memory: Optional[ConversationBufferMemory] = None,
        retriever_type: RetrieverType = "advanced",
        max_tokens: int = 10000,
        top_k: int = 15
    ):
        """Initialize the analysis chain.
        
        Args:
            llm: Language model to use
            memory: Optional conversation memory
            retriever_type: Type of retriever to use ('basic' or 'advanced')
            max_tokens: Maximum tokens for context building
            top_k: Number of top results to return
        """
        # Initialize tools
        self.content_retriever = ContentRetrievalTool(retriever_type=retriever_type)
        self.result_processor = ResultProcessorTool(top_k=top_k)
        self.response_generator = ResponseGeneratorTool(max_tokens=max_tokens)
        self.query_analyzer = QueryAnalysisTool() if retriever_type == "advanced" else None
        
        # Set up memory and LLM
        self.memory = memory or ConversationBufferMemory()
        self.llm = llm
        self.retriever_type = retriever_type
        self.top_k = top_k
        
        # Store intermediate steps
        self.intermediate_steps = []
        
    def _log_step(self, step_name: str, result: Union[str, Dict, List]) -> None:
        """Log intermediate step for transparency.
        
        Args:
            step_name: Name of the step
            result: Result from the step
        """
        formatted_result = result
        if isinstance(result, (dict, list)):
            formatted_result = {
                "type": "json",
                "content": result
            }
        else:
            formatted_result = {
                "type": "text",
                "content": str(result)
            }
            
        self.intermediate_steps.append({
            "step": step_name,
            "result": formatted_result
        })
        
    def run(self, query: str, callbacks: Optional[List] = None) -> str:
        """Execute the analysis chain.
        
        Args:
            query: User query to process
            callbacks: Optional list of callbacks for monitoring
            
        Returns:
            Generated response string
            
        Raises:
            Exception: If any step in the chain fails
        """
        # Reset intermediate steps
        self.intermediate_steps = []
        
        try:
            # Generate a unique run ID for this chain execution
            run_id = uuid4()
            
            # Start chain
            if callbacks:
                for callback in callbacks:
                    callback.on_chain_start(
                        serialized={"name": "AnalysisChain"},
                        inputs={"query": query},
                        run_id=run_id
                    )
            
            # 1. Query Analysis (if using advanced retriever)
            query_info = None
            if self.query_analyzer:
                # Start analysis step
                if callbacks:
                    for callback in callbacks:
                        callback.on_tool_start(
                            serialized={
                                "name": "analyzing query",
                                "block": "query_analysis"
                            },
                            input_str=query,
                            run_id=run_id
                        )
                
                # Run analysis
                query_info = self.query_analyzer.run(query)
                
                # Complete analysis step and start filter step
                if callbacks:
                    for callback in callbacks:
                        # Convert any Pydantic models to dict before serialization
                        output_dict = {}
                        for key, value in query_info.items():
                            if hasattr(value, 'model_dump'):
                                output_dict[key] = value.model_dump()
                            else:
                                output_dict[key] = value
                        
                        callback.on_tool_end(
                            output=json.dumps(output_dict),
                            run_id=run_id
                        )
                        if "analysis" in query_info:
                            # Start filter building
                            callback.on_tool_start(
                                serialized={
                                    "name": "building filters",
                                    "block": "query_analysis"
                                },
                                input_str=json.dumps(output_dict["analysis"]),
                                run_id=run_id
                            )
                            # Get filter dict
                            filter_dict = query_info.get("filter_dict", {})
                            # End filter building with result
                            callback.on_tool_end(
                                output=json.dumps({"filter_dict": filter_dict}),
                                run_id=run_id
                            )
                
                self._log_step("query_analysis", query_info)
            
            # 2. Content Retrieval
            if callbacks:
                for callback in callbacks:
                    callback.on_tool_start(
                        serialized={
                            "name": "retrieving results",
                            "block": "content_retrieval"
                        },
                        input_str=query,
                        run_id=run_id
                    )
            retrieval_output = self.content_retriever.run(query)
            if callbacks:
                for callback in callbacks:
                    # Convert retrieval output to dict if it's a Pydantic model
                    output_data = retrieval_output.model_dump() if hasattr(retrieval_output, 'model_dump') else retrieval_output
                    callback.on_tool_end(
                        output=json.dumps(output_data),
                        run_id=run_id
                    )
            self._log_step("content_retrieval", retrieval_output)
            
            # 3. Process Results
            if callbacks:
                for callback in callbacks:
                    callback.on_tool_start(
                        serialized={
                            "name": "grouping conversations",
                            "block": "content_retrieval"
                        },
                        input_str=json.dumps(retrieval_output),
                        run_id=run_id
                    )
            retrieval_result = self.result_processor.run(
                json.dumps(retrieval_output.model_dump() if hasattr(retrieval_output, 'model_dump') else retrieval_output)
            )
            if callbacks:
                for callback in callbacks:
                    callback.on_tool_end(
                        output=json.dumps(retrieval_result.model_dump() if hasattr(retrieval_result, 'model_dump') else retrieval_result),
                        run_id=run_id
                    )
            self._log_step("result_processing", retrieval_result)
            
            # 4. Response Generation
            # Ensure retrieval_result is properly serialized
            result_dict = retrieval_result.model_dump() if hasattr(retrieval_result, 'model_dump') else retrieval_result
            context = {
                "query": query,
                "retrieval_result": result_dict
            }
            if callbacks:
                for callback in callbacks:
                    callback.on_tool_start(
                        serialized={
                            "name": "building context",
                            "block": "response_generation"
                        },
                        input_str=json.dumps(context),
                        run_id=run_id
                    )
                    callback.on_tool_end(
                        output=json.dumps(context),
                        run_id=run_id
                    )
                    callback.on_tool_start(
                        serialized={
                            "name": "generating response",
                            "block": "response_generation"
                        },
                        input_str=json.dumps(context),
                        run_id=run_id
                    )
                    
            # Generate response using context
            final_output = self.response_generator.run(json.dumps(context))
            
            # Convert to dict if it's a Pydantic model
            final_dict = final_output.model_dump() if hasattr(final_output, 'model_dump') else final_output
            
            # Convert bullet points to markdown format in response
            if isinstance(final_dict, dict) and "response" in final_dict:
                final_dict["response"] = final_dict["response"].replace("\n•", "\n -")
            
            if callbacks:
                for callback in callbacks:
                    callback.on_tool_end(
                        output=json.dumps(final_dict),
                        run_id=run_id
                    )
                    callback.on_chain_end(
                        outputs={"output": final_dict},  # Pass the complete output including response and used_chunks
                        run_id=run_id
                    )
            
            self._log_step("response_generation", final_dict)
            return final_dict  # Return complete output with response and used_chunks
            
        except Exception as e:
            error_msg = f"Error during analysis: {str(e)}"
            self._log_step("error", error_msg)
            if callbacks:
                for callback in callbacks:
                    callback.on_tool_error(
                        error=e,
                        run_id=run_id
                    )
                    callback.on_chain_error(
                        error=e,
                        run_id=run_id
                    )
            raise Exception(error_msg)
