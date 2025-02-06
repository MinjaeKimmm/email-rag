import os
import pickle
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Callable, Optional
from dataclasses import dataclass
from tqdm import tqdm

from langchain_community.retrievers import BM25Retriever
from langchain.docstore.document import Document
from langchain_core.runnables import RunnableSerializable
from ..common.settings import EMBEDDINGS
from ..common.store import EmailStore

@dataclass
class ChunkMetadata:
    # Email-specific metadata
    conversation_id: str
    subject: str  # Changed from email_subject
    sender_name: str
    sender_email: str
    year: int  # Changed from received_time to separate fields
    month: int
    day: int
    
    # Chunk-specific metadata
    chunk_type: str  # 'email_body' or 'attachment'
    chunk_index: int
    total_chunks: int
    
    # For attachments
    attachment_metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to flat dictionary for Elasticsearch storage"""
        metadata_dict = {
            "conversation_id": self.conversation_id,
            "subject": self.subject,
            "sender_name": self.sender_name,
            "sender_email": self.sender_email,
            "year": self.year,
            "month": self.month,
            "day": self.day,
            "chunk_type": self.chunk_type,
            "chunk_index": self.chunk_index,
            "total_chunks": self.total_chunks,
        }
        
        # Add attachment metadata if present
        if self.attachment_metadata:
            for k, v in self.attachment_metadata.items():
                metadata_dict[f"attachment_{k}"] = v
                
        return metadata_dict

@dataclass
class Chunk:
    content: str
    metadata: ChunkMetadata
    
    @classmethod
    def from_langchain_document(cls, doc: Document, metadata: ChunkMetadata) -> 'Chunk':
        """Create a Chunk from a langchain Document"""
        return cls(content=doc.page_content, metadata=metadata)

class BaseChunker(ABC):
    def __init__(self, dataset: str):
        self.dataset = dataset
        self.embeddings = EMBEDDINGS

    @abstractmethod
    def get_name(self) -> str:
        """Names are used to distinguish by types of chunker and parameters (except dataset).
        Different class of chunkers or same class of chunkers with different parameters must always have different names.
        """
        pass

    @abstractmethod
    def get_splitter(self, doc_type: Optional[str] = None) -> Callable:
        """Returns a splitter function based on document type.
        Splitter function takes a string and returns a list of strings.
        """
        pass

    @abstractmethod
    def process_document(self, content: str, metadata: Dict[str, Any]) -> List[Chunk]:
        """Process a single document into chunks with metadata"""
        pass

    def create_embed(self):
        """Creates embeddings for all chunks"""
        # Get all chunks
        chunks = list(self.process_document())
        
        # Create embeddings
        embedder = EmailEmbedder(index_name=self.get_name())
        embedder.embed_chunks(chunks)
        
        return embedder.store

    def get_embed_retriever(self) -> RunnableSerializable:
        """Gets the embedding-based retriever"""
        # Initialize Elasticsearch store
        embedder = EmailEmbedder(index_name=self.get_name())
        
        # Return retriever
        return embedder.store.as_retriever()
    
    def get_bm25_file_name(self):
        """Gets the BM25 cache file name"""
        cache_file = f'{get_embedding_dirname(self.dataset)}/bm25_cache/{self.get_name()}.pkl'
        return cache_file

    def create_bm25(self):
        """Creates and caches BM25 retriever"""
        print('Creating new BM25 Retriever...')
        cache_file = self.get_bm25_file_name()
        if os.path.exists(cache_file):
            print('Found cache')
            return

        documents = []
        skipped_docs = 0
        print('Processing data...')
        for doc in tqdm(corpus_data[self.dataset].values()):
            if not doc.page_content.strip():
                skipped_docs += 1
                continue

            # Process the document using the new chunking logic
            chunks = self.process_document(doc.page_content, doc.metadata)
            for chunk in chunks:
                documents.append(Document(
                    page_content=chunk.content,
                    metadata=chunk.metadata.to_dict()
                ))

        print(f'Received {len(documents)} chunks')
        print(f'Example document: {documents[0]}')
        print('Creating BM25Retriever instance...')
        bm25_retriever = BM25Retriever.from_documents(documents, preprocess_func=simple_tokenizer)

        print('Saving BM25 Retriever to cache')
        with open(cache_file, 'wb') as f:
            pickle.dump(bm25_retriever, f)

    def get_bm25_retriever(self):
        """Gets the cached BM25 retriever"""
        self.create_bm25()
        cache_file = self.get_bm25_file_name()
        with open(cache_file, 'rb') as f:
            return pickle.load(f)