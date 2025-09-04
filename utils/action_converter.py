"""Utility class to convert PokerKit actions into human-readable text."""

class ActionConverter:
    """Utility class to convert PokerKit actions into human-readable text."""
    
    @staticmethod
    def to_human_readable(action, player_names=None) -> str:
        """Convert a PokerKit action to human-readable text.
        
        Args:
            action: The PokerKit action object
            player_names: Optional list of player names to use instead of "Player X"
        """
        if action is None:
            return None
            
        action_type = type(action).__name__
        
        # Helper function to get player name or fallback to "Player X"
        def get_player_name(player_index):
            if player_names and 0 <= player_index < len(player_names):
                return player_names[player_index]
            return f"Player {player_index}"
        
        # Handle different action types (including mock classes for testing)
        if action_type in ['Folding', 'MockFolding']:
            return f"{get_player_name(action.player_index)} folds"
            
        elif action_type in ['CheckingOrCalling', 'MockCheckingOrCalling']:
            if hasattr(action, 'amount') and action.amount > 0:
                return f"{get_player_name(action.player_index)} calls {action.amount}"
            else:
                return f"{get_player_name(action.player_index)} checks"
                
        elif action_type in ['CompletionBettingOrRaisingTo', 'MockCompletionBettingOrRaisingTo']:
            return f"{get_player_name(action.player_index)} raises to {action.amount}"
            
        elif action_type in ['BoardDealing', 'MockBoardDealing']:
            cards_str = ', '.join(str(card) for card in action.cards)
            return f"Board dealt: {cards_str}"
            
        elif action_type in ['HoleDealing', 'MockHoleDealing']:
            return f"{get_player_name(action.player_index)} dealt hole cards"
            
        elif action_type in ['BlindOrStraddlePosting', 'MockBlindOrStraddlePosting']:
            return f"{get_player_name(action.player_index)} posts blind: {action.amount}"
            
        elif action_type in ['AntePosting', 'MockAntePosting']:
            return f"{get_player_name(action.player_index)} posts ante: {action.amount}"
            
        elif action_type in ['ChipsPulling', 'MockChipsPulling']:
            return f"{get_player_name(action.player_index)} pulls chips: {action.amount}"
            
        elif action_type in ['ChipsPushing', 'MockChipsPushing']:
            # Handle chips pushing to show who won the hand
            if hasattr(action, 'amounts') and action.amounts:
                winners = []
                for i, amount in enumerate(action.amounts):
                    if amount > 0:
                        winners.append(f"{get_player_name(i)} wins {amount}")
                
                if winners:
                    if len(winners) == 1:
                        return f"🏆 {winners[0]}"
                    else:
                        return f"🏆 {' and '.join(winners)}"
                else:
                    return "No winners (split pot)"
            else:
                return "Chips pushed"
            
        elif action_type in ['HandKilling', 'MockHandKilling']:
            return f"{get_player_name(action.player_index)} mucks hand"
            
        elif action_type in ['CardBurning', 'MockCardBurning']:
            return "Card burned"
            
        elif action_type in ['HoleCardsShowingOrMucking', 'MockHoleCardsShowingOrMucking']:
            if hasattr(action, 'hole_cards') and action.hole_cards:
                cards_str = ', '.join(str(card) for card in action.hole_cards)
                return f"{get_player_name(action.player_index)} shows: {cards_str}"
            else:
                return f"{get_player_name(action.player_index)} mucks hand"

        # You can ignore these actions
        elif action_type in ['BetCollection']:
            return ""
            
        else:
            # Fallback for unknown action types
            print(f"ERROR RENDERING ACTION: {action_type}")
            if hasattr(action, 'player_index') and hasattr(action, 'amount'):
                return f"{action_type}: {get_player_name(action.player_index)}, Amount {action.amount}"
            elif hasattr(action, 'player_index'):
                return f"{action_type}: {get_player_name(action.player_index)}"
            else:
                return f"{action_type}" 