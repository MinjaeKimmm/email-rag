from typing import Any, Dict, List, Optional
from langchain_core.runnables import RunnableLambda
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from .settings import LLM

class BaseAgent(RunnableLambda):
    """Base agent class that can be used with Langchain's Runnable interface."""
    
    def __init__(self):
        super().__init__(self._run)
        self.llm = LLM
    
    def get_example_messages(self) -> List[Dict[str, str]]:
        """Return example messages for the agent. Override this in subclasses.
        
        Returns:
            List of message dictionaries with 'role' and 'content' keys.
            Role must be one of: 'system', 'user', 'assistant'
        """
        raise NotImplementedError
    
    def get_prompt(self, input_data: Any) -> str:
        """Return the prompt for the agent. Override this in subclasses."""
        raise NotImplementedError
    
    def validate_output(self, output: str) -> Optional[Dict]:
        """Validate the LLM output. Override this in subclasses."""
        raise NotImplementedError
    
    def _run(self, input_data: Any, max_retries: int = 3) -> Optional[Dict]:
        """Run the agent on the input data."""
        messages = []
        for msg in self.get_example_messages():
            if msg['role'] == 'system':
                messages.append(SystemMessage(content=msg['content']))
            elif msg['role'] == 'user':
                messages.append(HumanMessage(content=msg['content']))
            elif msg['role'] == 'assistant':
                messages.append(AIMessage(content=msg['content']))
        
        messages.append(HumanMessage(content=self.get_prompt(input_data)))
        
        for attempt in range(max_retries):
            try:
                response = self.llm.invoke(messages)
                result = self.validate_output(response.content)
                if result:
                    return result
            except Exception as e:
                print(f"Error on attempt {attempt + 1}: {str(e)}")
                if attempt == max_retries - 1:
                    raise
        
        return None
