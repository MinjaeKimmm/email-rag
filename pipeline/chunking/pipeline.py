import json
from pathlib import Path
from typing import List, Dict, Any
from tqdm import tqdm
from ..common.settings import get_project_root

from .conversation_processor import ConversationProcessor
from .document_chunker import DocumentChunker
from .embed import EmailEmbedder

class EmailProcessingPipeline:
    def __init__(self, dataset: str = "email"):
        """Initialize pipeline components
        
        Args:
            dataset: Name of the dataset to process (default: "email")
        """
        self.dataset = dataset
        self.conversation_processor = ConversationProcessor(dataset=dataset)
        self.document_chunker = DocumentChunker(dataset)
        self.embedder = EmailEmbedder()

    def process_emails(self, input_file: str = None):
        """Process emails from JSON, chunk them, and create embeddings"""
        if input_file is None:
            input_file = str(Path(__file__).parent.parent.parent / 'data' / 'processed_emails' / 'included_emails.json')
        
        print("=== Starting Email Processing Pipeline ===")
        
        # First check if we have complete embeddings
        doc_count = self.embedder.store.client.count(index=self.embedder.store.index_name)['count']
        status = self.embedder._get_embedding_status()
        print(f"Current index status: {status} with {doc_count} documents")
        
        if status == "COMPLETE" and doc_count > 0:
            print("Found complete embeddings, no need to reprocess")
            return
        
        print(f"Processing emails from: {input_file}")
        print("Loading conversations...")
        conversations = self._load_conversations(input_file)
        print(f"Loaded {len(conversations)} conversations\n")
        
        print("Processing conversations into chunks...")
        all_chunks = []
        for conv in tqdm(conversations, ascii=True):
            # Process the conversation and get chunks
            chunks = list(self.conversation_processor.process_conversation(conv))
            all_chunks.extend(chunks)
        
        print(f"\nGenerated {len(all_chunks)} chunks")
        print("\n=== Starting Embedding Process ===")
        
        # Create embeddings
        self.embedder.embed_chunks(all_chunks)
        
        #print("\n=== Cleaning Up Small Chunks ===")
        # Remove chunks that are too small
        #self.embedder.remove_small_chunks()
        
        print("\n=== Pipeline Complete ===")

    def _load_conversations(self, input_file: str) -> List[Dict[str, Any]]:
        """Load conversations from JSON file"""
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Extract conversation data from the nested structure
            return [item['conversation'] for item in data]


def run_embed(input_file: str = "included_emails.json", dataset: str = "email"):
    """
    Process emails into chunks and create embeddings.
    
    Args:
        input_file: Name of the input JSON file in the processed_emails directory (default: included_emails.json)
        dataset: Name of the dataset to process (default: "email")
    """
    data_dir = get_project_root() / "data" / "processed_emails"
    input_path = data_dir / input_file
    
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
        
    print(f"Processing and embedding emails from {input_file}...")
    pipeline = EmailProcessingPipeline(dataset=dataset)
    pipeline.process_emails(input_file=str(input_path))
