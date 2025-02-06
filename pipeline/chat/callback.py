"""Callback handlers for the analysis pipeline."""
from typing import Any, Dict, List, Optional
from uuid import UUID
from langchain.callbacks.base import BaseCallbackHandler
import streamlit as st
import json

def format_json_for_html(json_obj: Any) -> str:
    """Format JSON object for HTML display with proper indentation and spacing.
    
    Args:
        json_obj: Any JSON-serializable object
        
    Returns:
        Formatted HTML string with proper indentation and line breaks
    """
    # First get the basic formatted JSON with 4-space indentation
    raw_json = json.dumps(json_obj, indent=4, ensure_ascii=False)
    
    # Process the JSON string to fix formatting
    lines = []
    for line in raw_json.splitlines():
        # Count leading spaces for indentation
        leading_spaces = len(line) - len(line.lstrip())
        # Replace leading spaces with &nbsp;
        if leading_spaces > 0:
            line = '&nbsp;' * (leading_spaces * 2) + line.lstrip()
        
        # Remove spaces after { and [
        line = line.replace('{ ', '{').replace('[ ', '[')
        # Remove spaces before } and ]
        line = line.replace(' }', '}').replace(' ]', ']')
        
        lines.append(line)
    
    # Join with HTML newlines
    return '<br>'.join(lines)

class AnalysisPipelineCallbackHandler(BaseCallbackHandler):
    """Callback handler for the analysis pipeline with Streamlit progress display."""
    def __init__(self, steps_container, response_container):
        self.steps_container = steps_container
        self.response_container = response_container
        
        # Define our blocks/thoughts with their expandability
        self.thought_blocks = {
            "query_analysis": self.steps_container.expander("Query Analysis", expanded=True),
            "content_retrieval": self.steps_container.expander("Content Retrieval", expanded=True),
            "response_generation": self.steps_container.expander("Response Generation", expanded=True)
        }
        
        # Define the steps and their states for each block
        self.steps = {
            "query_analysis": {
                "analyzing_query": {
                    "current": None, 
                    "placeholder": None, 
                    "complete": False,
                    "result": None  # To store analysis result
                },
                "building_filters": {
                    "current": None, 
                    "placeholder": None, 
                    "complete": False,
                    "result": None  # To store filter result
                }
            },
            "content_retrieval": {
                "retrieving": {
                    "current": None,
                    "placeholder": None,
                    "complete": False
                },
                "grouping": {
                    "current": None,
                    "placeholder": None,
                    "complete": False
                }
            },
            "response_generation": {
                "building_context": {
                    "current": None,
                    "placeholder": None,
                    "complete": False
                },
                "generating": {
                    "current": None,
                    "placeholder": None,
                    "complete": False
                }
            }
        }

    def _update_step(self, block: str, step: str, message: str, complete: bool = False, result: Any = None):
        """Update a specific step within a block"""
        target = self.steps[block][step]
        
        # Create placeholder if doesn't exist
        if not target["placeholder"]:
            with self.thought_blocks[block]:
                target["placeholder"] = st.empty()
        
        # Update status
        icon = "✅" if complete else "⏳"
        target["current"] = message
        target["complete"] = complete
        
        # Show message in the appropriate block
        with self.thought_blocks[block]:
            target["placeholder"].markdown(f"{icon} {message}")
            
            # Show result if available and complete
            if complete and result:
                # If result is a string that looks like JSON, parse it
                if isinstance(result, str):
                    try:
                        result = json.loads(result)
                    except json.JSONDecodeError:
                        pass
                # Format JSON with proper indentation and spacing
                formatted_json_html = format_json_for_html(result)
                
                # Create HTML with proper styling and the formatted JSON
                st.markdown(
                    f"""<div style='margin: 0.5em 0 1em 0; border: 2px solid #6b7280; border-radius: 0.5em; box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);'>
                        <details>
                            <summary style='cursor: pointer; padding: 0.5em 1em; user-select: none;'>...</summary>
                            <div style='background-color: #f0f2f6; margin: 0; padding: 1em 1em 1em 2em; border-top: 1px solid #6b7280; font-family: monospace; overflow-x: auto;'>{formatted_json_html}</div>
                        </details>
                    </div>""",
                    unsafe_allow_html=True
                )

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs
    ) -> None:
        """Handle tool start events"""
        tool_name = serialized.get("name", "").lower()
        
        if "analyzing query" in tool_name.lower():
            self._update_step("query_analysis", "analyzing_query", "Analyzing query...")
        elif "building filter" in tool_name.lower():
            self._update_step("query_analysis", "building_filters", "Building query filters...")
        elif "retrieving" in tool_name.lower():
            self._update_step("content_retrieval", "retrieving", "Retrieving results...")
        elif "grouping" in tool_name.lower():
            self._update_step("content_retrieval", "grouping", "Grouping conversations...")
        elif "building context" in tool_name.lower():
            self._update_step("response_generation", "building_context", "Building context...")
        elif "generating" in tool_name.lower():
            self._update_step("response_generation", "generating", "Generating response...")

    def on_tool_end(
        self,
        output: str,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs
    ) -> None:
        """Handle tool completion events"""
        # Convert string output to dict if possible
        try:
            output_dict = json.loads(output) if isinstance(output, str) else output
        except:
            output_dict = {"output": output}
            
        # Determine which step completed based on output structure
        if isinstance(output_dict, dict):
            if "analysis" in output_dict:
                self._update_step("query_analysis", "analyzing_query", 
                                "Query analysis complete", True, output_dict["analysis"])
            elif "filter_dict" in output_dict:
                self._update_step("query_analysis", "building_filters", 
                                "Query filters built", True, output_dict["filter_dict"])
            elif "results" in output_dict:
                self._update_step("content_retrieval", "retrieving", 
                                "Results retrieved", True)
            elif "conversation_groups" in str(output_dict):
                self._update_step("content_retrieval", "grouping", 
                                "Conversations grouped", True)
            elif "context" in output_dict:
                self._update_step("response_generation", "building_context", 
                                "Context built", True)
            elif "response" in output_dict:
                self._update_step("response_generation", "generating", 
                                "Response generated", True)

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs
    ) -> None:
        """Handle tool errors"""
        error_msg = str(error)
        
        # Only show error for the current incomplete step
        current_block = None
        current_step = None
        
        # Find the current incomplete step
        for block in self.steps:
            for step in self.steps[block]:
                if not self.steps[block][step]["complete"]:
                    current_block = block
                    current_step = step
                    break
            if current_block:
                break
        
        # Show error only for the current step
        if current_block and current_step:
            with self.thought_blocks[current_block]:
                st.error(f"❌ Error in {current_step}: {error_msg}")

    def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs
    ) -> None:
        """Reset state when chain starts"""
        for block in self.steps:
            for step in self.steps[block]:
                self.steps[block][step] = {
                    "current": None,
                    "placeholder": None,
                    "complete": False,
                    "result": None
                }

    def _format_source_content(self, chunk: Dict[str, Any]) -> str:
        """Format source content with error handling for missing fields."""
        try:
            metadata = chunk.get('metadata', {})
            content = chunk.get('content', '')
            reason = chunk.get('reason', 'Relevant to your query')
            
            # Get metadata with defaults
            subject = metadata.get('subject', 'No subject')
            sender = metadata.get('sender_name', 'Unknown sender')
            year = metadata.get('year', '----')
            month = metadata.get('month', '--')
            day = metadata.get('day', '--')
            
            chunk_type = metadata.get('chunk_type', 'unknown')
                                    
            # Format content preview
            content_preview = content[:4000] if len(content) > 4000 else content
            if len(content) > 4000:
                content_preview += '...'
            
            return f"""
### Email Details
**Subject**: {subject}  
**From**: {sender}  
**Date**: {year}-{month}-{day}  
**Relevant Portion**: {reason}  
**Relevant Content Type**: {chunk_type}  

### Relevant Content Portion:
```email
{content_preview}
```""".strip()
        except Exception as e:
            return f"Error formatting source: {str(e)}"

    def on_chain_end(
        self,
        outputs: Dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs
    ) -> None:
        """Handle chain completion with sources."""
        output = outputs.get("output", {})
        response = output.get("response", "")
        used_chunks = output.get("used_chunks", [])

        # Display response
        with self.response_container:
            # Show the main response
            st.info(response)
            
            if used_chunks:
                with st.expander("📚 View Sources", expanded=False):
                    # Limit number of visible sources
                    MAX_VISIBLE_SOURCES = 15
                    visible_chunks = used_chunks[:MAX_VISIBLE_SOURCES]
                    
                    if len(used_chunks) > MAX_VISIBLE_SOURCES:
                        st.warning(f"Showing top {MAX_VISIBLE_SOURCES} sources out of {len(used_chunks)}")
                    
                    # Create tabs for visible sources
                    source_tabs = st.tabs([f"Source {i+1}" for i in range(len(visible_chunks))])
                    
                    # Fill each tab with source content
                    for tab, chunk in zip(source_tabs, visible_chunks):
                        with tab:
                            st.markdown(self._format_source_content(chunk))

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs
    ) -> None:
        """Handle chain errors"""
        error_msg = str(error)
        for block in self.steps:
            for step in self.steps[block]:
                if not self.steps[block][step]["complete"]:
                    if block == "query_analysis":
                        with self.thought_blocks[block]:
                            st.error(f"❌ Error in {step}: {error_msg}")
                    else:
                        st.error(f"❌ Error in {step}: {error_msg}")
                self.steps[block][step] = {
                    "current": None,
                    "placeholder": None,
                    "complete": False,
                    "result": None
                }
