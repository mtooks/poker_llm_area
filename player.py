"""Player module for Poker RL agents."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence, Optional

import openai  # type: ignore
from google import genai  # type: ignore

class Player:
    """Player class that encapsulates LLM interaction and player state."""

    def __init__(
        self,
        name: str,
        provider: str,  # "openai" | "gemini"
        model: str,
        initial_stack: int = 400,
        system_prompt: Optional[str] = None,
    ):
        self.name = name
        self.provider = provider
        self.model = model
        self.stack = initial_stack
        self.hand_history = []
        self.conversation_history = []
        self.system_prompt = system_prompt or (
            """You are an autonomous No limit TEXAS HOLDEM poker agent, evaluating the current game state and making the 
            decision to fold, check, call, or raise that maximizes your expected value.
            Return EXACTLY one token from the user's 'legal' list. If you want to
            raise, use the format 'raise_to:<amount>'. Amount is a singular integer that has to be within the range provided.
            The range of valid bet sizes is provided to you. A response like 'raise_to:6900 to 500' is not allowed. 
            You are also provided with your hole cards, the current street, and the past board history.\n"
            Justify your decision but separate it from the token with the '@' symbol"""
        )
        
        # Initialize LLM clients once during object creation
        import os
        from pathlib import Path
        from dotenv import load_dotenv
        
        # Load environment variables from .env file if it exists
        env_path = Path(os.path.dirname(os.path.abspath(__file__))) / '.env'
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
            
        if self.provider == "openai":
            openai_key = os.getenv("OPENAI_KEY", "")
            if not openai_key:
                raise ValueError("OPENAI_KEY environment variable is not set")
            self.client = openai.AsyncOpenAI(api_key=openai_key)
        elif self.provider == "gemini":
            gemini_key = os.getenv("GEMINI_KEY", "")
            if not gemini_key:
                raise ValueError("GEMINI_KEY environment variable is not set")
            genai.configure(api_key=gemini_key)
            self.client = genai.GenerativeModel(self.model)

    async def _chat_openai(self, messages: Sequence[Dict[str, str]]) -> str:
        """Send messages to OpenAI API and get response using persistent client."""
        # Use the existing client instead of creating a new one
        rsp = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
            max_tokens=400,
        )
        return rsp.choices[0].message.content.strip()

    async def _chat_gemini(self, messages: Sequence[Dict[str, str]]) -> str:
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

    async def ask(self, messages: Sequence[Dict[str, str]]) -> str:
        """Route request to appropriate LLM provider with conversation history."""
        # Combine system message, conversation history, and current message
        full_messages = [{"role": "system", "content": self.system_prompt}]
        full_messages.extend(self.conversation_history)
        
        # Only add the last user message if it's not already in conversation history
        if messages and messages[-1]["role"] == "user" and (not self.conversation_history or 
                                                          messages[-1] != self.conversation_history[-1]):
            full_messages.append(messages[-1])
        
        if self.provider == "openai":
            response = await self._chat_openai(full_messages)
        elif self.provider == "gemini":
            response = await self._chat_gemini(full_messages)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")
        
        # Update conversation history with user's message and AI's response
        if messages and messages[-1]["role"] == "user" and (not self.conversation_history or 
                                                          messages[-1] != self.conversation_history[-1]):
            self.conversation_history.append(messages[-1])
        self.conversation_history.append({"role": "assistant", "content": response})
        
        return response

    async def make_decision(self, game_state: Dict[str, Any], legal_actions: List[str]) -> str:
        """Ask the LLM to make a decision based on game state and legal actions."""
        prompt_json = json.dumps(
            {
                "state": game_state,
                "legal": legal_actions,
            },
            separators=(',', ':'),
        )
        
        # Only send the user message since system prompt and history are handled in ask()
        messages = [
            {"role": "user", "content": prompt_json},
        ]
        
        return await self.ask(messages)
    
    def update_stack(self, new_stack: int) -> None:
        """Update player's stack size."""
        self.stack = new_stack
        
    def update_memory(self, hand_result: Dict[str, Any]) -> None:
        """Store hand result in player's memory."""
        self.hand_history.append(hand_result)
        
        # Add hand summary to conversation history for context in future hands
        summary = f"Hand #{hand_result['hand_id']} summary: "
        summary += f"Starting stack {hand_result['starting_stacks'][0] if self.name == 'P0' else hand_result['starting_stacks'][1]}, "
        summary += f"Ending stack {hand_result['result']['final_stacks'][0] if self.name == 'P0' else hand_result['result']['final_stacks'][1]}, "
        summary += f"Profit {hand_result['result']['profit_p0'] if self.name == 'P0' else hand_result['result']['profit_p1']}"
        
        self.conversation_history.append({"role": "user", "content": summary})
        
    def reset_conversation_for_new_hand(self):
        """Reset conversation history for a new hand while preserving hand summaries."""
        # Keep only the system prompt and hand summaries
        new_history = []
        for msg in self.conversation_history:
            if msg["role"] == "user" and "Hand #" in msg["content"] and "summary" in msg["content"]:
                new_history.append(msg)
        self.conversation_history = new_history
