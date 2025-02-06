import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic_settings import BaseSettings

load_dotenv()

# LLM settings
LLM_PROVIDER = "openai"
LLM_MODEL = "gpt-4o-mini"
LLM = ChatOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    model=LLM_MODEL,
    temperature=0
)

# Embedding settings
EMBEDDINGS = OpenAIEmbeddings(model="text-embedding-3-small")

# Elasticsearch settings
ELASTIC_URL = os.getenv("ELASTIC_URL", "http://localhost:9200")
ELASTIC_USER = os.getenv("ELASTIC_USER", "elastic")
ELASTIC_PASSWORD = os.getenv("ELASTIC_PASSWORD", "linqalpha")
ELASTIC_DEFAULT_INDEX = os.getenv("ELASTIC_DEFAULT_INDEX", "emails")

def get_project_root() -> Path:
    """Get the root directory of the project"""
    return Path(__file__).parent.parent.parent

def get_embedding_dirname(strategy_name: str = "parent_child") -> Path:
    """Get the directory for storing embeddings"""
    embed_dir = get_project_root() / "embed" / strategy_name
    embed_dir.mkdir(parents=True, exist_ok=True)
    return embed_dir


def get_llm_with_streaming() -> ChatOpenAI:
    """Get a copy of the LLM with streaming enabled."""
    settings = LLM.model_dump()
    if 'streaming' in settings:
        del settings['streaming']
    return ChatOpenAI(
        **settings,
        streaming=True
    )
