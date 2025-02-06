"""Generator for answering questions using email context."""
from typing import Dict, List, Optional
from datetime import datetime
import json
from ..common.base_agent import BaseAgent
from pipeline.common.prompt import GENERATOR_PROMPT_TEMPLATE 
from pipeline.common.example_messages import get_generator_messages

class Generator(BaseAgent):
    def __init__(self):
        super().__init__()
        self._current_input = None
        
    def _run(self, input_data: Dict, max_retries: int = 3) -> Optional[Dict]:
        """Store input_data for validation and call parent's _run"""
        self._current_input = input_data
        return super()._run(input_data, max_retries)
        
    def get_example_messages(self) -> List[Dict[str, str]]:
        """Return example messages showing how to answer email questions."""
        return get_generator_messages()

    def get_prompt(self, input_data: Dict) -> str:
        """Format prompt with context and query."""
        current_date = datetime.now()
        return GENERATOR_PROMPT_TEMPLATE.format(
            query=input_data['query'],
            context=input_data['context'].context_text,
            month=current_date.month,
            year=current_date.year
        )


    def validate_output(self, output: str) -> Optional[Dict]:
        """Validate response format and chunk references."""
        try:
            parsed = json.loads(output)
            
            # Check required fields
            required = ["thought_process", "response", "answer"]
            if not all(k in parsed for k in required):
                print("Missing required fields in response")
                return None
                
            # Validate thought process
            if not isinstance(parsed["thought_process"], list):
                print("thought_process must be a list")
                return None
                
            # Validate answer format
            if not isinstance(parsed["answer"], dict):
                print("answer must be a dictionary")
                return None
                
            # Validate chunk IDs using stored input_data
            if self._current_input and 'context' in self._current_input:
                available_chunks = set(self._current_input['context'].chunk_ids)
                for chunk_id in parsed["answer"].keys():
                    try:
                        # Ensure chunk_id is numeric
                        if not chunk_id.isdigit():
                            print(f"Chunk ID must be numeric: {chunk_id}")
                            return None
                        if chunk_id not in available_chunks:
                            print(f"Invalid chunk ID in response: {chunk_id}")
                            print(f"Available chunks were: {available_chunks}")
                            return None
                    except Exception as e:
                        print(f"Error validating chunk ID {chunk_id}: {e}")
                        return None
                
            return parsed
        except json.JSONDecodeError as e:
            print(f"Failed to parse response as JSON: {e}")
            return None
        except Exception as e:
            print(f"Validation error: {e}")
            return None
