"""Module for preprocessing email content before classification and RAG processing."""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

class EmailPreprocessor:
    """Preprocesses email content for better classification and RAG processing."""
    
    def __init__(self):
        # Common patterns to clean
        self.url_pattern = re.compile(r'<https?://[^>]+>')
        self.email_pattern = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')
        self.quote_pattern = re.compile(r'^>.*$', re.MULTILINE)
        self.signature_pattern = re.compile(r'(-{2,}|\_{2,}|={2,}|Best regards|Sincerely|Thanks|Thank you|BR,|Best,).*', re.DOTALL | re.IGNORECASE)
        self.thread_pattern = re.compile(r'On.*wrote:|From:.*Sent:|To:.*Subject:', re.MULTILINE | re.IGNORECASE)
        
        # Unicode patterns
        self.zero_width_chars = re.compile(r'[\u200B-\u200F\u202A-\u202E\uFEFF]')
        self.special_spaces = re.compile(r'[\xa0\u2000-\u200A\u202F\u205F\u3000]')
        
    def clean_html(self, text: str) -> str:
        """Remove HTML tags while preserving important text."""
        if not text:
            return ""
            
        # First extract text with BeautifulSoup
        soup = BeautifulSoup(text, "html.parser")
        
        # Remove script and style elements
        for element in soup(["script", "style"]):
            element.decompose()
            
        # Get text content
        text = soup.get_text()
        
        # Remove HTML comments
        text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
        
        return text
        
    def normalize_whitespace(self, text: str) -> str:
        """Normalize all forms of whitespace."""
        if not text:
            return ""
            
        # Replace zero-width and special space characters
        text = self.zero_width_chars.sub('', text)
        text = self.special_spaces.sub(' ', text)
        
        # Normalize newlines
        text = re.sub(r'[\r\n]+', '\n', text)
        
        # Remove tabs
        text = re.sub(r'\t+', ' ', text)
        
        # Normalize multiple spaces
        text = re.sub(r' {2,}', ' ', text)
        
        # Ensure paragraphs are preserved with double newlines
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        return text.strip()
        
    def clean_urls_and_emails(self, text: str) -> str:
        """Clean URLs and email addresses."""
        if not text:
            return ""
            
        # Replace URLs with <URL> placeholder
        text = self.url_pattern.sub('<URL>', text)
        
        # Replace tracking URLs
        text = re.sub(r'https?://\S*tracking\S+', '', text)
        
        # Replace email addresses with <EMAIL> placeholder
        text = self.email_pattern.sub('<EMAIL>', text)
        
        return text
        
    def remove_quotes_and_signatures(self, text: str) -> str:
        """Remove email quotes, signatures, and thread markers."""
        if not text:
            return ""
            
        # Remove quoted text
        text = self.quote_pattern.sub('', text)
        
        # Remove signatures
        text = self.signature_pattern.sub('', text)
        
        # Remove thread markers
        text = self.thread_pattern.sub('', text)
        
        return text
        
    def clean_formatting(self, text: str) -> str:
        """Clean special formatting characters and normalize punctuation."""
        if not text:
            return ""
            
        # Normalize bullet points
        text = re.sub(r'^\s*[-*•]\s+', '- ', text, flags=re.MULTILINE)
        
        # Normalize exclamation marks
        text = re.sub(r'!+', '.', text)
        
        # Remove repeated words (possible template artifacts)
        text = re.sub(r'(\b\w+\b)( \1\b)+', r'\1', text)
        
        return text
        
    def preprocess_email_body(self, body: str) -> str:
        """Main method to preprocess email body text."""
        if not body:
            return ""
            
        # Apply preprocessing steps in sequence
        text = self.clean_html(body)
        text = self.normalize_whitespace(text)
        text = self.clean_urls_and_emails(text)
        text = self.remove_quotes_and_signatures(text)
        text = self.clean_formatting(text)
        
        # Final whitespace normalization
        text = self.normalize_whitespace(text)
        
        return text
        
    def preprocess_conversations(self, conversations: List[Dict]) -> List[Dict]:
        """Preprocess all conversations in the dataset."""
        processed_conversations = []
        
        for conv in conversations:
            processed_conv = conv.copy()
            processed_messages = []
            
            for msg in conv['Messages']:
                processed_msg = msg.copy()
                processed_msg['Body'] = self.preprocess_email_body(msg['Body'])
                processed_messages.append(processed_msg)
                
            processed_conv['Messages'] = processed_messages
            processed_conversations.append(processed_conv)
            
        return processed_conversations
        
def preprocess_email_data(input_path: str, output_path: str):
    """Process the email conversations JSON file and save preprocessed version."""
    logger.info(f"Loading email conversations from {input_path}")
    
    with open(input_path, 'r', encoding='utf-8') as f:
        conversations = json.load(f)
        
    preprocessor = EmailPreprocessor()
    processed_conversations = preprocessor.preprocess_conversations(conversations)
    
    logger.info(f"Saving preprocessed conversations to {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(processed_conversations, f, indent=2, ensure_ascii=False)
        
    logger.info("Preprocessing complete!")
    
if __name__ == "__main__":
    # Example usage
    input_file = "data/email_conversations.json"
    output_file = "data/email_conversations_preprocessed.json"
    preprocess_email_data(input_file, output_file)
