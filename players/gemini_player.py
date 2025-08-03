"""Gemini player implementation for Poker RL agents."""

import os
from pathlib import Path
from typing import Sequence, Dict

# Handle optional imports
try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False

from .base_player import BasePlayer


class GeminiPlayer(BasePlayer):
    """Gemini-specific player implementation."""

    def __init__(
        self,
        name: str,
        model: str,
        initial_stack: int = 400,
        system_prompt: str = None,
    ):
        super().__init__(name, model, initial_stack, system_prompt)
        
        # Initialize Gemini client
        self._setup_gemini_client()

    def _setup_gemini_client(self):
        """Setup Gemini client with API key."""
        if not GEMINI_AVAILABLE:
            raise ImportError("Gemini provider requires the 'google-generativeai' package. Install with 'pip install google-generativeai'")
        
        if not DOTENV_AVAILABLE:
            raise ImportError("Gemini provider requires the 'python-dotenv' package. Install with 'pip install python-dotenv'")
        
        # Load environment variables from .env file if it exists
        env_path = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / '.env'
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
            
        gemini_key = os.getenv("GEMINI_KEY", "")
        if not gemini_key:
            raise ValueError("GEMINI_KEY environment variable is not set")
        
        genai.configure(api_key=gemini_key)
        self.client = genai.GenerativeModel(self.model)

    async def _chat(self, messages: Sequence[Dict[str, str]]) -> str:
        """Send the prompt to Gemini via persistent client."""
        # Build the full conversation history for context
        full_history = ""
        for msg in messages:
            if msg["role"] == "system":
                full_history += f"<system>\n{msg['content']}\n</system>\n"
            elif msg["role"] == "user":
                full_history += f"<user>\n{msg['content']}\n</user>\n"
            elif msg["role"] == "assistant":
                full_history += f"<assistant>\n{msg['content']}\n</assistant>\n"
        
        resp = self.client.generate_content(full_history)
        return resp.text.strip() 