# Email RAG System

## Overview

This project implements a Retrieval-Augmented Generation (RAG) system for Microsoft Outlook emails, using the email contents, metadatas, and attachments for vector search and advanced vector search with metadata filtering. The system provides an interactive chat interface for natural language queries to test the entire pipeline.

## Repository Structure

```
email-rag/
├── data/                   # Data directory for processed emails and embeddings
├── pipeline/
│   ├── common/            # Global settings, LLM configurations, base agent definitions, prompts
│   ├── preprocess/        # Email and attachment preprocessing
│   ├── filter/            # Email classification and conversation filtering
│   ├── chunking/          # Content chunking (email, PDF, DOCX, XLSX) and embedding logic
│   ├── retrieval/         # Vector search with metadata filtering, conversation grouping
│   ├── generation/        # Response generation components
│   ├── eval/              # QA dataset creation and retrieval evaluation
│   ├── chat/             # Chatbot implementation and interface
│   ├── tests/            # Pipeline component testing
│   └── util/             # Utility functions
├── main.py               # Pipeline entry point
├── requirements.txt      # Python dependencies
├── setup.py             # Package configuration
├── .env                 # Environment variables
├── docker-compose.yml   # Docker configuration for Elasticsearch
├── outlook_email.py     # Outlook email extraction utility
└── .gitignore          # Git ignore configurations
```

## Features

- **Email Processing**: Handles various email formats and attachments (PDF, DOCX, XLSX)
- **Smart Filtering**: Classifies and filters emails based on relevance and conversation context
- **Semantic Search**: Uses vector embeddings for intelligent content retrieval
- **Conversation Grouping**: Groups related emails for context preservation
- **Interactive Chat**: Web-based UI for natural language interaction with email content
- **Evaluation Tools**: Built-in tools for assessing retrieval quality

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/MinjaeKimmm/email-rag.git
   cd email-rag
   ```

2. **Set up data directory**
   - Unzip the provided data folder and place it in the project root directory:
   ```
   email-rag/
   ├── data/              # Place the unzipped data folder here
   ├── pipeline/
   └── ...
   ```

3. **Configure environment variables**
   - Create a `.env` file based on `.env.example`:
   ```env
   # OpenAI settings
   OPENAI_API_KEY=your-openai-key

   # Elasticsearch settings
   ELASTIC_VERSION=8.17.1
   ELASTIC_PASSWORD=your-elastic-password
   ES_JAVA_OPTS=-Xmx2g -Xms2g
   ```

4. **Build and run with Docker**
   ```bash
   docker compose up --build
   ```
   - Initial setup takes approximately 10 minutes for:
     - Building Docker images
     - Setting up Elasticsearch
     - Processing and embedding documents

5. **Access the application**
   - Open [http://localhost:8501](http://localhost:8501) in your browser
   - Use the chat interface to interact with your email data
