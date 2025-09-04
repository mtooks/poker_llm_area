"""Base player class for Poker RL agents."""

from __future__ import annotations

import json
import time
from pathlib import Path
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence, Optional
from dotenv import load_dotenv


class BasePlayer(ABC):
    """Abstract base class for all poker players."""

    def __init__(
        self,
        name: str,
        model: str,
        initial_stack: int = 400,
        system_prompt: Optional[str] = None,
        enable_reflection: bool = False,
    ):
        self.name = name
        self.model = model
        self.stack = initial_stack
        self.initial_stack = initial_stack
        self.hand_history = []
        self.conversation_history = []
        self.system_prompt = system_prompt or self._get_default_system_prompt()
        self.structured_system_prompt = self._get_structured_system_prompt()
        self.enable_reflection = enable_reflection
        
        # Add tracking for strategic decisions
        self.decision_times = []
        self.position_stats = {"Button": {}, "Big Blind": {}}
        self.bluff_attempts = 0
        self.bluff_successes = 0
        self.value_bets = 0
        self.value_bet_successes = 0
        self.player_index = None  # Will be set in update_memory
        self.illegal_moves = 0
        
        # Add player notes - a space for the player to record observations
        self.notes = ""
        self.reflections = []  # Store hand reflections for analysis
        
        # Track current hand for memory management
        self.current_hand_id = None
        
        # Store detailed hand summaries for memory
        self.hand_summaries = []

    
    def _get_structured_system_prompt(self) -> str:
        """Get the default system prompt for poker players."""
        return """You are a seasoned and experienced No limit Texas Holdem poker player, evaluating the current game state and making the decision 
        to fold, check, call, or raise to win as much money as possible. Do not fold when you are not facing a bet. Playing safe is not neccesarily the best strategy. Think about what 
        cards you have, which ones your opponents have, and what you could represent. Given this, then decide whether or not it is a good time to bluff. When you 
        have a bad hand, think about what you could represent to your opponents. If you have a good hand, think about how to extract the maxmium value from your opponents.        
        You can maintain notes about your observations of the game. These notes will be shown to you in each decision to help you adapt your strategy over time. Add useful information about your opponent's tendencies, your own statistics, and reminders of effective strategies.
        Output your action in the given structured format. Return an action from the ones provided, and the amount if raising, as well as your reasoning and notes if you want to take them.
        You will also be passed a a history of previous games with the actiona taken by previous players. Use this in your decision making.

       """

    def _get_default_system_prompt(self) -> str:
        """Get the default system prompt for poker players."""
        return """You are a seasoned and experienced No limit Texas Holdem poker player, evaluating the current game state and making the decision 
        to fold, check, call, or raise to win as much money as possible. Do not fold when you are not facing a bet. Playing safe is not neccesarily the best strategy. Think about what 
        cards you have, which ones your opponents have, and what you could represent. Given this, then decide whether or not it is a good time to bluff. When you 
        have a bad hand, think about what you could represent to your opponents. If you have a good hand, think about how to extract the maxmium value from your opponents.        
        Response format:Output must be: <action>[optional integer]@<brief reason>. No other characters, no markdown. If you're raising, the optional integer range will be provided to you in the legal tokens. Explain your thinking but separate it from the token with a preceding '@' symbol
        You will also be passed a a history of previous games with the actiona taken by previous players. Use this in your decision making.
        You can maintain notes about your observations of the game. These notes will be shown to you in each decision to help you adapt your strategy over time. Add useful information about your opponent's tendencies, your own statistics, and reminders of effective strategies.
        """


    @abstractmethod
    async def _chat(self, messages: Sequence[Dict[str, str]]) -> str:
        """Send messages to the LLM provider and get response."""
        pass

    

    async def ask(self, messages: Sequence[Dict[str, str]]) -> str:
        """Route request to appropriate LLM provider with intelligent memory management."""
        # Start with system prompt
        full_messages = [{"role": "system", "content": self.system_prompt}]

        # Add summarized memory from previous hands
        if self.hand_history:
            memory_summary = self._create_memory_summary()
            if memory_summary:
                full_messages.append({
                    "role": "user", 
                    "content": f"Previous hands summary:\n{memory_summary}"
                })

        # Add current hand conversation history (detailed)
        current_hand_messages = self._get_current_hand_messages()
        full_messages.extend(current_hand_messages)
        
        # Add the current message if it's not already in conversation history
        if messages and messages[-1]["role"] == "user" and (not self.conversation_history or 
                                                          messages[-1] != self.conversation_history[-1]):
            full_messages.append(messages[-1])
        
        response = await self._chat(full_messages)
        
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
    
    async def make_showdown_decision(self, game_state: Dict[str, Any], legal_actions: List[str]) -> str:
        """Ask the LLM whether to show or muck at showdown."""
        start_time = time.time()
        
        # Add showdown-specific context to game state
        showdown_context = {
            **game_state,
            "situation": "showdown",
            "decision_type": "show_or_muck",
            "context": "Decide whether to reveal your hole cards or muck them face-down",
            "considerations": [
                "Showing reveals your playing style to opponents",
                "Mucking keeps your strategy hidden", 
                "Table image and future hands matter",
                "Information warfare is part of poker strategy"
            ],
            "notes": self.notes
        }
        
        prompt_json = json.dumps(
            {
                "state": showdown_context,
                "legal": legal_actions,
                "instructions": "Choose 'show' to reveal your cards or 'muck' to fold face-down. Consider your table image and information strategy.",
            },
            separators=(',', ':'),
        )
        
        messages = [
            {"role": "user", "content": prompt_json},
        ]
        
        response = await self.ask(messages)
        
        # Track decision time
        decision_time = time.time() - start_time
        self.decision_times.append(decision_time)
        
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
    
    async def reflect_on_hand(self, hand_summary: str) -> str:
        """Ask the LLM to reflect on a completed hand and extract lessons."""
        if not self.enable_reflection:
            return ""
        
        reflection_prompt = {
            "hand_summary": hand_summary,
            "current_notes": self.notes,
            "task": "reflection",
            "instructions": [
                "Analyze the completed hand and your decisions",
                "Identify what you did well and what could be improved", 
                "Consider opponent tendencies you observed",
                "Extract key lessons for future hands",
                "Update your strategic understanding"
            ],
            "output_format": "Provide 2-3 key insights and any strategic adjustments you want to make. Be concise but specific."
        }
        
        prompt_json = json.dumps(reflection_prompt, separators=(',', ':'))
        messages = [{"role": "user", "content": prompt_json}]
        
        try:
            reflection = await self.ask(messages)
            
            # Store the reflection for analysis
            self.reflections.append({
                "hand_summary": hand_summary,
                "reflection": reflection,
                "timestamp": len(self.hand_history)  # Use hand count as timestamp
            })
            
            return reflection
        except Exception as e:
            print(f"Error during reflection for {self.name}: {e}")
            return ""
    
    def update_notes(self, new_notes: str) -> None:
        """Update the player's notes about the game."""
        if not new_notes:
            return
            
        # Append to existing notes
        self.notes += f"\n{new_notes}"
    
    def _create_human_readable_hand_summary(self, hand_result: Dict[str, Any]) -> str:
        """Create a concise, human-readable summary of a completed hand."""
        from utils.action_converter import ActionConverter
        
        hand_id = hand_result['hand_id']
        player_names = hand_result.get('player_names', [])
        
        # Find this player's position in the hand
        dealer_pos = hand_result.get('dealer_position', 0)
        my_position = None
        my_hole_cards = None
        my_profit = 0
        
        # Determine player's position and cards
        for i, name in enumerate(player_names):
            if name == self.name:
                my_position = i
                my_hole_cards = hand_result.get('hole_cards', {}).get(i, [])
                my_profit = hand_result['result'].get(f'profit_p{i}', 0)
                break
        
        # Start building summary
        summary = f"Hand #{hand_id}: "
        
        # Add hole cards if available
        if my_hole_cards:
            cards_str = ', '.join(str(card) for card in my_hole_cards)
            summary += f"Dealt {cards_str}. "
        
        # Convert PokerKit operations to human-readable actions
        if 'pokerkit_operations' in hand_result:
            actions = []
            board_cards_dealt = 0  # Track how many board cards have been dealt
            
            for op in hand_result['pokerkit_operations']:
                readable = ActionConverter.to_human_readable(op, player_names)
                if readable and readable.strip():  # Only include non-empty actions
                    
                    # Skip redundant hole card dealing messages
                    if "dealt hole cards" in readable.lower():
                        continue
                    
                    # Replace "Board dealt" with proper street names
                    if readable.startswith("Board dealt:"):
                        cards_in_this_deal = len(readable.split(", ")) - 1  # Subtract 1 for "Board dealt:"
                        if board_cards_dealt == 0:
                            # First board dealing is always the flop (3 cards)
                            readable = readable.replace("Board dealt:", "Flop:")
                            board_cards_dealt += 3
                        elif board_cards_dealt == 3:
                            # Second board dealing is the turn (1 card)
                            readable = readable.replace("Board dealt:", "Turn:")
                            board_cards_dealt += 1
                        elif board_cards_dealt == 4:
                            # Third board dealing is the river (1 card)
                            readable = readable.replace("Board dealt:", "River:")
                            board_cards_dealt += 1
                    
                    actions.append(readable + ".")
            
            if actions:
                # Filter out some noise (like card burning, bet collection, chips operations)
                filtered_actions = [action for action in actions if not any(x in action.lower() for x in [
                    'card burned', 'chips pushed', 'chips pulled'
                ])]
                if filtered_actions:
                    summary += " ".join(filtered_actions) + ". "
        
        # Add final board if available
        if hand_result.get('final_board'):
            board_str = ', '.join(str(card) for card in hand_result['final_board'])
            summary += f"Final board: {board_str}. "
        
        # Add outcome
        if my_profit > 0:
            summary += f"Won {my_profit} chips."
        elif my_profit < 0:
            summary += f"Lost {abs(my_profit)} chips."
        else:
            summary += "Broke even."
        
        return summary
       
    
    async def update_memory(self, hand_result: Dict[str, Any]) -> None:
        """Store hand result in player's memory and update statistics."""
        self.hand_history.append(hand_result)
        
        # Set current hand ID for memory management
        self.current_hand_id = hand_result.get('hand_id')
        
        # Create human-readable hand summary using ActionConverter
        summary = self._create_human_readable_hand_summary(hand_result)
        
        # Store detailed hand summary for memory
        self.hand_summaries.append(summary)
        
        # Keep only the last 5 detailed summaries to avoid overwhelming context
        if len(self.hand_summaries) > 5:
            self.hand_summaries = self.hand_summaries[-5:]
        
        # Optional reflection on the completed hand
        if self.enable_reflection:
            try:
                reflection = await self.reflect_on_hand(summary)
                if reflection:
                    # Add reflection to conversation history as assistant message
                    self.conversation_history.append({
                        "role": "assistant", 
                        "content": f"Hand reflection: {reflection}"
                    })
            except Exception as e:
                print(f"Could not run reflection for {self.name}: {e}")
        
        # Clear conversation history for the next hand (keep only reflections and notes)
        self._clear_conversation_for_new_hand()
        
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
    
    def _clear_conversation_for_new_hand(self):
        """Clear conversation history for the next hand, keeping only reflections and notes."""
        # Keep only reflections and notes for the next hand
        new_history = []
        for msg in self.conversation_history:
            # Keep reflections
            if msg["role"] == "assistant" and "Hand reflection:" in msg["content"]:
                new_history.append(msg)
            # Keep notes reminders
            elif msg["role"] == "user" and "Your current notes:" in msg["content"]:
                new_history.append(msg)
        
        self.conversation_history = new_history
    
    def update_stack(self, new_stack: int) -> None:
        """Update player's stack size."""
        self.stack = new_stack
    
    def _create_memory_summary(self) -> str:
        """Create a detailed summary of previous hands for context."""
        if not self.hand_summaries:
            return ""
        
        # Add overall performance stats
        total_wins = sum(1 for hand in self.hand_history if hand["result"].get(f"profit_p{self.player_index}", 0) > 0)
        win_rate = (total_wins / len(self.hand_history)) * 100 if self.hand_history else 0
        
        # Combine detailed hand summaries
        detailed_summaries = "\n".join(self.hand_summaries)
        
        summary = f"Previous hands summary:\n{detailed_summaries}\n\nOverall win rate: {win_rate:.1f}%"
        
        # Add strategic notes if available
        if self.notes:
            summary += f"\nYour notes: {self.notes}"
        
        return summary
    
    def _get_current_hand_messages(self) -> List[Dict[str, str]]:
        """Get conversation messages for the current hand only."""
        if not self.conversation_history:
            return []
        
        current_hand_messages = []
        for msg in self.conversation_history:
            # Include all messages that don't contain hand summaries
            if msg["role"] == "user" and "Hand #" in msg["content"]:
                # Skip hand summary messages (they're handled by memory summary)
                continue
            current_hand_messages.append(msg)
        
        return current_hand_messages 