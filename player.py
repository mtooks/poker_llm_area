"""Player module for Poker RL agents."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence, Optional
import time

import openai  
from google import genai 

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
        self.initial_stack = initial_stack
        self.hand_history = []
        self.conversation_history = []
        self.system_prompt = system_prompt or (
            """You are the most aggresive talented and skilled professional No limit Texas Holdem poker player, evaluating the current game state and making the decision to fold, check, call, or raise to win as much money as possible.         
            Response format:Output must be: <action>[optional integer]@<brief reason>. No other characters, no markdown. If you're raising, the optional integer range will be provided to you in the legal tokens. Explain your thinking but separate it from the token with a preceding '@' symbol
            
            You can maintain notes about your observations of the game. These notes will be shown to you in each decision to help you adapt your strategy over time. Add useful information about your opponent's tendencies, your own statistics, and reminders of effective strategies.
            """)
        
        # Add tracking for strategic decisions
        self.decision_times = []
        self.position_stats = {"Button": {}, "Big Blind": {}}
        self.bluff_attempts = 0
        self.bluff_successes = 0
        self.value_bets = 0
        self.value_bet_successes = 0
        self.player_index = None  # Will be set in update_memory
        
        # Add player notes - a space for the player to record observations
        self.notes = ""
        
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
        elif self.provider == "anthropic":
            # Import Anthropic library - handle this at initialization time
            # to avoid requiring it for users who don't use Anthropic
            try:
                import anthropic
            except ImportError:
                raise ImportError("Anthropic provider requires the 'anthropic' package. Install with 'pip install anthropic'")
            
            anthropic_key = os.getenv("ANTHROPIC_KEY", "")
            if not anthropic_key:
                raise ValueError("ANTHROPIC_KEY environment variable is not set")
            self.client = anthropic.AsyncAnthropic(api_key=anthropic_key)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

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

    async def _chat_anthropic(self, messages: Sequence[Dict[str, str]]) -> str:
        """Send messages to Anthropic API and get response."""
        # Convert from OpenAI-style messages to Anthropic format
        system_content = ""
        conversation = []
        
        # Extract system message
        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
                break
        
        # Build the conversation messages
        for msg in messages:
            if msg["role"] == "user":
                conversation.append({"role": "user", "content": msg["content"]})
            elif msg["role"] == "assistant":
                conversation.append({"role": "assistant", "content": msg["content"]})
        
        # Create the message request
        response = await self.client.messages.create(
            model=self.model,
            system=system_content,
            # temperature = 
            messages=conversation,
            max_tokens=1000
        )
        
        return response.content[0].text

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
        elif self.provider == "anthropic":
            response = await self._chat_anthropic(full_messages)
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
        start_time = time.time()
        
        # Add notes to the game state
        game_state["notes"] = self.notes
        game_state["can_update_notes"] = True
        
        prompt_json = json.dumps(
            {
                "state": game_state,
                "legal": legal_actions,
                "instructions": "You can update your notes by including a line starting with 'NOTES:' after your action and commentary.",
            },
            separators=(',', ':'),
        )
        
        # Only send the user message since system prompt and history are handled in ask()
        messages = [
            {"role": "user", "content": prompt_json},
        ]
        
        response = await self.ask(messages)
        
        # Track decision time
        decision_time = time.time() - start_time
        self.decision_times.append(decision_time)
        
        # Track position-based decisions
        position = game_state.get("Position", "Unknown")
        if position not in self.position_stats:
            self.position_stats[position] = {"decisions": 0, "aggressive_actions": 0}
        
        self.position_stats[position]["decisions"] = self.position_stats[position].get("decisions", 0) + 1
        if response.startswith("raise_to:"):
            self.position_stats[position]["aggressive_actions"] = self.position_stats[position].get("aggressive_actions", 0) + 1
        
        # Check if player wants to update their notes
        lines = response.split("\n")
        action_line = lines[0]
        note_lines = []
        
        for i, line in enumerate(lines):
            if line.startswith("NOTES:"):
                note_lines = lines[i:]
                break
        
        if note_lines:
            # Update notes
            self.update_notes("\n".join(note_line[6:].strip() for note_line in note_lines))
            # Return only the action part
            return action_line
            
        return response
    
    def update_notes(self, new_notes: str) -> None:
        """Update the player's notes about the game."""
        if not new_notes:
            return
            
        # Append to existing notes
        if self.notes:
            self.notes += f"\n{new_notes}"
        else:
            self.notes = new_notes
    
    def update_memory(self, hand_result: Dict[str, Any]) -> None:
        """Store hand result in player's memory and update statistics."""
        self.hand_history.append(hand_result)
        
        # Add hand summary to conversation history for context in future hands
        summary = f"Hand #{hand_result['hand_id']} summary: "
        summary += f"Starting stack {hand_result['starting_stacks'][0] if self.name == 'P0' else hand_result['starting_stacks'][1]}, "
        summary += f"Ending stack {hand_result['result']['final_stacks'][0] if self.name == 'P0' else hand_result['result']['final_stacks'][1]}, "
        summary += f"Profit {hand_result['result']['profit_p0'] if self.name == 'P0' else hand_result['result']['profit_p1']}"
        
        self.conversation_history.append({"role": "user", "content": summary})
        
        # Add a reminder about notes to the conversation history for future hands
        if self.notes:
            self.conversation_history.append({
                "role": "user", 
                "content": f"Your current notes:\n{self.notes}"
            })
        
        # Additional tracking for strategic patterns
        for action in hand_result["actions"]:
            if action["player"] == self.player_index:  # Need to track player_index
                # Analyze if this was a bluff (holding weak cards but betting/raising)
                if action["action"].startswith("raise_to:") and "bluff" in action.get("commentary", "").lower():
                    self.bluff_attempts += 1
                    if hand_result["result"].get(f"profit_p{self.player_index}", 0) > 0:
                        self.bluff_successes += 1
                
                # Analyze if this was a value bet (holding strong cards and betting/raising)
                if action["action"].startswith("raise_to:") and "value" in action.get("commentary", "").lower():
                    self.value_bets += 1
                    if hand_result["result"].get(f"profit_p{self.player_index}", 0) > 0:
                        self.value_bet_successes += 1

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Return comprehensive performance metrics for this player."""
        metrics = {
            "total_profit": self.stack - self.initial_stack,
            "win_rate": sum(1 for hand in self.hand_history if hand["result"].get(f"profit_p{self.player_index}", 0) > 0) / len(self.hand_history) if self.hand_history else 0,
            "avg_decision_time": sum(self.decision_times) / len(self.decision_times) if self.decision_times else 0,
            "position_stats": self.position_stats,
            "bluff_success_rate": self.bluff_successes / self.bluff_attempts if self.bluff_attempts > 0 else 0,
            "value_bet_success_rate": self.value_bet_successes / self.value_bets if self.value_bets > 0 else 0,
            "notes": self.notes
        }
        return metrics
    
    def reset_conversation_for_new_hand(self):
        """Reset conversation history for a new hand while preserving hand summaries."""
        # Keep only the system prompt and hand summaries
        new_history = []
        for msg in self.conversation_history:
            if msg["role"] == "user" and "Hand #" in msg["content"] and "summary" in msg["content"]:
                new_history.append(msg)
        self.conversation_history = new_history
    
    def update_stack(self, new_stack: int) -> None:
        """Update player's stack size."""
        self.stack = new_stack
