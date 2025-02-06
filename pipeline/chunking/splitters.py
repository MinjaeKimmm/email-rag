from typing import List, Dict, Any
from langchain_experimental.text_splitter import SemanticChunker
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.schema import Document
from dataclasses import dataclass
import re

from .base import Chunk, ChunkMetadata
from ..common.settings import EMBEDDINGS

# Default settings for character-based splitting
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 50

# Settings for semantic chunking
MIN_CHUNK_SIZE = 500

class DocumentSplitter:
    """Base class for document splitters"""
    def __init__(self, embeddings=None):
        self.embeddings = embeddings or EMBEDDINGS
        self.semantic_chunker = SemanticChunker(
            self.embeddings,
            min_chunk_size=MIN_CHUNK_SIZE
        )
        self.default_chunker = RecursiveCharacterTextSplitter(
            chunk_size=DEFAULT_CHUNK_SIZE,
            chunk_overlap=DEFAULT_CHUNK_OVERLAP
        )

    def split_document(self, content: str, metadata: Dict[str, Any]) -> List[Chunk]:
        """Split document into chunks with metadata"""
        raise NotImplementedError

class PDFSplitter(DocumentSplitter):
    """Splitter for PDF documents using semantic chunking"""
    def split_document(self, content: str, metadata: Dict[str, Any]) -> List[Chunk]:
        # If content is smaller than chunk size, don't split
        if len(content) <= DEFAULT_CHUNK_SIZE:
            doc = Document(page_content=content)
            return [
                Chunk.from_langchain_document(
                    doc,
                    ChunkMetadata(
                        conversation_id=metadata.get('conversation_id', ''),
                        subject=metadata.get('subject', ''),
                        sender_name=metadata.get('sender_name', ''),
                        sender_email=metadata.get('sender_email', ''),
                        year=metadata.get('year', 1900),
                        month=metadata.get('month', 1),
                        day=metadata.get('day', 1),
                        chunk_type='pdf',
                        chunk_index=0,
                        total_chunks=1,
                        attachment_metadata=metadata.get('attachment_metadata', {})
                    )
                )
            ]
        
        # Use semantic chunking for larger PDFs
        chunks = self.semantic_chunker.split_text(content)
        # Convert chunks to langchain Documents
        docs = [Document(page_content=chunk) for chunk in chunks]
        return [
            Chunk.from_langchain_document(
                doc,
                ChunkMetadata(
                    conversation_id=metadata.get('conversation_id', ''),
                    subject=metadata.get('subject', ''),
                    sender_name=metadata.get('sender_name', ''),
                    sender_email=metadata.get('sender_email', ''),
                    year=metadata.get('year', 1900),
                    month=metadata.get('month', 1),
                    day=metadata.get('day', 1),
                    chunk_type='pdf',
                    chunk_index=idx,
                    total_chunks=len(docs),
                    attachment_metadata=metadata.get('attachment_metadata', {})
                )
            )
            for idx, doc in enumerate(docs)
        ]

class DocxSplitter(DocumentSplitter):
    """Splitter for DOCX documents using semantic chunking"""
    def split_document(self, content: str, metadata: Dict[str, Any]) -> List[Chunk]:
        # If content is smaller than chunk size, don't split
        if len(content) <= DEFAULT_CHUNK_SIZE:
            doc = Document(page_content=content)
            return [
                Chunk.from_langchain_document(
                    doc,
                    ChunkMetadata(
                        conversation_id=metadata.get('conversation_id', ''),
                        subject=metadata.get('subject', ''),
                        sender_name=metadata.get('sender_name', ''),
                        sender_email=metadata.get('sender_email', ''),
                        year=metadata.get('year', 1900),
                        month=metadata.get('month', 1),
                        day=metadata.get('day', 1),
                        chunk_type='docx',
                        chunk_index=0,
                        total_chunks=1,
                        attachment_metadata=metadata.get('attachment_metadata', {})
                    )
                )
            ]
        
        # Use semantic chunking for larger documents
        chunks = self.semantic_chunker.split_text(content)
        # Convert chunks to langchain Documents
        docs = [Document(page_content=chunk) for chunk in chunks]
        return [
            Chunk.from_langchain_document(
                doc,
                ChunkMetadata(
                    conversation_id=metadata.get('conversation_id', ''),
                    subject=metadata.get('subject', ''),
                    sender_name=metadata.get('sender_name', ''),
                    sender_email=metadata.get('sender_email', ''),
                    year=metadata.get('year', 1900),
                    month=metadata.get('month', 1),
                    day=metadata.get('day', 1),
                    chunk_type='docx',
                    chunk_index=idx,
                    total_chunks=len(docs),
                    attachment_metadata=metadata.get('attachment_metadata', {})
                )
            )
            for idx, doc in enumerate(docs)
        ]

class XLSXSplitter(DocumentSplitter):
    """Splitter for XLSX documents using sheet-based chunking"""
    def split_document(self, content: str, metadata: Dict[str, Any]) -> List[Chunk]:
        # Split by sheets using "Sheet:" marker
        sheet_chunks = []
        current_chunk = []
        current_sheet = None
        
        for line in content.split('\n'):
            if line.startswith('Sheet:'):
                # When we find a new sheet, save the previous one if it exists
                if current_sheet and current_chunk:
                    sheet_chunks.append((current_sheet, '\n'.join(current_chunk)))
                current_sheet = line[6:].strip()  # Remove "Sheet: " prefix
                current_chunk = [line]
            else:
                if current_sheet:  # Only append if we're inside a sheet
                    current_chunk.append(line)
        
        # Don't forget to add the last sheet
        if current_sheet and current_chunk:
            sheet_chunks.append((current_sheet, '\n'.join(current_chunk)))
        
        # Convert chunks to Chunk objects with metadata
        return [
            Chunk(
                content=chunk_content,
                metadata=ChunkMetadata(
                    conversation_id=metadata.get('conversation_id', ''),
                    subject=metadata.get('subject', ''),
                    sender_name=metadata.get('sender_name', ''),
                    sender_email=metadata.get('sender_email', ''),
                    year=metadata.get('year', 1900),
                    month=metadata.get('month', 1),
                    day=metadata.get('day', 1),
                    chunk_type='xlsx',
                    chunk_index=idx,
                    total_chunks=len(sheet_chunks),
                    attachment_metadata={
                        **metadata.get('attachment_metadata', {}),
                        'sheet_name': sheet_name
                    }
                )
            )
            for idx, (sheet_name, chunk_content) in enumerate(sheet_chunks)
        ]
