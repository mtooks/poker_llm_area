"""Track PnL (Profit and Loss) per hand for graphing."""

import csv
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional


class PnLTracker:
    """Track cumulative PnL for each player after each hand."""
    
    def __init__(self, output_dir: str = "results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Initialize tracking
        self.run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.csv_file = self.output_dir / f"pnl_{self.run_timestamp}.csv"
        self.cumulative_pnl = {}  # Track cumulative PnL per player: {player_name: cumulative_pnl}
        self.initial_stacks = {}  # Track initial stacks: {player_name: initial_stack}
        
        # Initialize CSV file with header
        self._initialize_csv()
    
    def _initialize_csv(self):
        """Create CSV file with header."""
        with open(self.csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                "hand_number",
                "player_name",
                "hand_profit",
                "cumulative_pnl",
                "stack_after_hand"
            ])
    
    def initialize_players(self, players: List[Any]):
        """Initialize player tracking with their initial stacks."""
        for player in players:
            self.initial_stacks[player.name] = player.initial_stack
            self.cumulative_pnl[player.name] = 0
    
    def record_hand(
        self,
        hand_number: int,
        players: List[Any],
        hand_data: Dict[str, Any]
    ):
        """Record PnL for each player after a hand completes.
        
        Args:
            hand_number: The hand number (0-indexed)
            players: List of player objects in position order
            hand_data: Hand data dict containing result information
        """
        starting_stacks = hand_data.get("starting_stacks", [])
        result = hand_data.get("result", {})
        
        # Get player names in position order
        player_names = hand_data.get("player_names", [player.name for player in players])
        
        # Append to CSV
        with open(self.csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            
            for idx, player in enumerate(players):
                player_name = player_names[idx] if idx < len(player_names) else player.name
                
                # Calculate hand profit (profit for this specific hand)
                if idx < len(starting_stacks):
                    hand_profit = result.get(f"profit_p{idx}", 0)
                else:
                    # Fallback: calculate from stack difference
                    hand_profit = player.stack - (starting_stacks[idx] if idx < len(starting_stacks) else player.initial_stack)
                
                # Update cumulative PnL
                if player_name not in self.cumulative_pnl:
                    self.cumulative_pnl[player_name] = 0
                self.cumulative_pnl[player_name] += hand_profit
                
                # Write row
                writer.writerow([
                    hand_number,
                    player_name,
                    hand_profit,
                    self.cumulative_pnl[player_name],
                    player.stack
                ])
    
    def get_csv_path(self) -> str:
        """Get the path to the CSV file."""
        return str(self.csv_file)

