"""Streamlit application for email analysis."""
import os
import time
from typing import Optional

import streamlit as st
from langchain.memory import ConversationBufferMemory

from pipeline.common.settings import get_llm_with_streaming
from pipeline.chat.chain import AnalysisChain
from pipeline.chat.callback import AnalysisPipelineCallbackHandler


def stream_response(response: str, placeholder) -> str:
    """Stream response with typing effect in info box."""
    displayed_response = ""
    for char in response:
        displayed_response += char
        placeholder.info(displayed_response + "▌")
        time.sleep(0.01)
    placeholder.info(displayed_response)
    return displayed_response


def init_session_state() -> None:
    """Initialize session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "chain" not in st.session_state:
        st.session_state.advanced_retrieval = True
        st.session_state.top_k = 15
        st.session_state.max_tokens = 10000
        
        llm = get_llm_with_streaming()
        st.session_state.chain = AnalysisChain(
            llm=llm,
            memory=ConversationBufferMemory(),
            retriever_type="advanced",
            top_k=st.session_state.top_k,
            max_tokens=st.session_state.max_tokens
        )


def update_chain_if_needed(
    advanced_retrieval: bool,
    top_k: int,
    max_tokens: int
) -> None:
    """Update chain if settings have changed."""
    settings_changed = False
    
    # Check each setting
    if advanced_retrieval != st.session_state.advanced_retrieval:
        st.session_state.advanced_retrieval = advanced_retrieval
        settings_changed = True
    
    if top_k != st.session_state.top_k:
        st.session_state.top_k = top_k
        settings_changed = True
    
    if max_tokens != st.session_state.max_tokens:
        st.session_state.max_tokens = max_tokens
        settings_changed = True
    
    # Reinitialize chain if needed
    if settings_changed:
        llm = get_llm_with_streaming()
        st.session_state.chain = AnalysisChain(
            llm=llm,
            memory=ConversationBufferMemory(),
            retriever_type="advanced" if advanced_retrieval else "basic",
            top_k=top_k,
            max_tokens=max_tokens
        )


def create_streamlit_app() -> None:
    """Create and run the Streamlit application."""
    st.set_page_config(
        page_title="LinqAlpha Email Analysis Assistant",
        page_icon="📧",
        layout="wide"
    )

    # Title and description
    st.title("📧 LinqAlpha Email Analysis Assistant")
    st.markdown("""
    Ask questions about LinqAlpha internal financial email data!
    - 📨 Search and analyze through emails
    - 🔍 Advanced search and retrieval capabilities
    """)

    # Initialize session state
    init_session_state()

    # Create sidebar with settings
    with st.sidebar:
        st.header("Settings")
        st.markdown("Customize your analysis experience")
        
        # Advanced retrieval toggle
        advanced_retrieval = st.toggle(
            "Use Advanced Retrieval",
            value=st.session_state.advanced_retrieval,
            help="Enable sophisticated query analysis and filtering"
        )
        
        # Top K slider
        top_k = st.slider(
            "Number of Email Conversations Retrieved",
            min_value=5,
            max_value=50,
            value=st.session_state.top_k,
            help="Number of most relevant email chunks to analyze"
        )
        
        # Max tokens slider
        max_tokens = st.slider(
            "Max Email Context Input Tokens for LLM",
            min_value=1000,
            max_value=30000,
            value=st.session_state.max_tokens,
            help="Maximum amount of email context to consider"
        )
        
        # Update chain if settings changed
        update_chain_if_needed(advanced_retrieval, top_k, max_tokens)

    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant":
                # Show the main response
                st.info(message["content"])
                
                # Show sources if available
                used_chunks = message.get("used_chunks", [])
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
                                    
                                    st.markdown(f"""
### Email Details
**Subject**: {subject}  
**From**: {sender}  
**Date**: {year}-{month}-{day}  
**Relevant Portion**: {reason}  
**Relevant Content Type**: {chunk_type}  

### Relevant Content Portion:
```email
{content_preview}
```""".strip())
                                except Exception as e:
                                    st.error(f"Error displaying source: {str(e)}")
            else:
                st.markdown(message["content"])

    # Get user input
    if question := st.chat_input("Ask me anything about your emails and documents"):
        # Add user message to chat history
        st.session_state.messages.append({
            "role": "user",
            "content": question
        })

        # Display user message
        with st.chat_message("user"):
            st.markdown(question)

        # Display assistant response
        with st.chat_message("assistant"):
            # Create containers for steps and response
            steps_container = st.container()
            response_container = st.container()

            try:
                # Create callback handler with separate containers for steps and response
                callback_handler = AnalysisPipelineCallbackHandler(
                    steps_container,
                    response_container
                )

                # Run chain with callback
                full_output = st.session_state.chain.run(
                    question,
                    callbacks=[callback_handler]
                )

                # Add to chat history with sources
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": full_output.get("response", ""),
                    "used_chunks": full_output.get("used_chunks", [])
                })

            except Exception as e:
                st.error(f"An error occurred: {str(e)}")


if __name__ == "__main__":
    create_streamlit_app()
