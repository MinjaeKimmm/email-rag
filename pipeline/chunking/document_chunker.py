from typing import List, Dict, Any, Optional, Callable
from .base import BaseChunker, Chunk, ChunkMetadata
from .splitters import PDFSplitter, DocxSplitter, XLSXSplitter, DocumentSplitter

class DocumentChunker(BaseChunker):
    def __init__(self, dataset: str):
        super().__init__(dataset)
        # Initialize document type specific splitters
        self._splitters = {
            '.pdf': PDFSplitter(self.embeddings),
            '.docx': DocxSplitter(self.embeddings),
            '.xlsx': XLSXSplitter(self.embeddings)
        }
        
    def get_splitter(self, doc_type: Optional[str] = None) -> DocumentSplitter:
        """Get appropriate splitter based on document type"""
        if doc_type in self._splitters:
            return self._splitters[doc_type]
        # Return any splitter for default handling since they all have the same default_chunker
        return self._splitters['.pdf']

    def get_name(self) -> str:
        return f"document_chunker_{self.dataset}"

    def process_document(self, content: str, metadata: Dict[str, Any]) -> List[Chunk]:
        """Process a document (email or attachment) into chunks"""
        # Initialize global chunk tracking if not present
        if not hasattr(self, '_current_chunk_index'):
            self._current_chunk_index = 0
            self._total_chunks = 0
        
        # First pass to count total chunks
        if 'ConversationID' in metadata and 'Messages' in metadata:
            chunks = self._process_email_body(content, metadata, count_only=True)
        elif 'extension' in metadata:
            chunks = self._process_attachment(content, metadata, count_only=True)
        else:
            chunks = self._process_default(content, metadata, count_only=True)
        self._total_chunks += len(chunks)
        
        # Second pass to actually process with global indices
        if 'ConversationID' in metadata and 'Messages' in metadata:
            chunks = self._process_email_body(content, metadata)
        elif 'extension' in metadata:
            chunks = self._process_attachment(content, metadata)
        else:
            chunks = self._process_default(content, metadata)
            
        return chunks

    def _process_email_body(self, content: str, metadata: Dict[str, Any], count_only: bool = False) -> List[Chunk]:
        """Process email body as a single chunk"""
        if count_only:
            return [None]  # Just return a list of length 1
            
        message = metadata['Messages'][0]  # Assuming first message
        # Parse received time into year, month, day
        received_time = message['ReceivedTime']
        year = int(received_time[:4])
        month = int(received_time[5:7])
        day = int(received_time[8:10])
        
        chunk = Chunk(
            content=content,
            metadata=ChunkMetadata(
                conversation_id=metadata['ConversationID'],
                subject=message['Subject'],
                sender_name=message['SenderName'],
                sender_email=message['SenderEmail'],
                year=year,
                month=month,
                day=day,
                chunk_type='email_body',
                chunk_index=self._current_chunk_index,
                total_chunks=self._total_chunks
            )
        )
        self._current_chunk_index += 1
        return [chunk]

    def _process_attachment(self, content: str, metadata: Dict[str, Any], count_only: bool = False) -> List[Chunk]:
        """Process attachment using appropriate splitter"""
        doc_type = metadata['extension']
        
        if doc_type in self._splitters:
            chunks = self._splitters[doc_type].split_document(content, metadata)
            if count_only:
                return [None] * len(chunks)
                
            # Update global indices
            for chunk in chunks:
                chunk.metadata.chunk_index = self._current_chunk_index
                chunk.metadata.total_chunks = self._total_chunks
                self._current_chunk_index += 1
            return chunks
            
        return self._process_default(content, metadata, count_only)

    def _process_default(self, content: str, metadata: Dict[str, Any], count_only: bool = False) -> List[Chunk]:
        """Default processing for unknown document types"""
        # Use default chunker from any splitter (they all have the same default)
        chunks = self._splitters['.pdf'].default_chunker.split_text(content)
        if count_only:
            return [None] * len(chunks)
            
        result = []
        for chunk_content in chunks:
            chunk = Chunk(
                content=chunk_content,
                metadata=ChunkMetadata(
                    conversation_id=metadata.get('conversation_id', ''),
                    subject=metadata.get('subject', ''),
                    sender_name=metadata.get('sender_name', ''),
                    sender_email=metadata.get('sender_email', ''),
                    year=metadata.get('year', 1900),
                    month=metadata.get('month', 1),
                    day=metadata.get('day', 1),
                    chunk_type='unknown',
                    chunk_index=self._current_chunk_index,
                    total_chunks=self._total_chunks,
                    attachment_metadata=metadata.get('attachment_metadata', {})
                )
            )
            result.append(chunk)
            self._current_chunk_index += 1
        return result
