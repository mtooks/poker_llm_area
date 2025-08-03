"""Utility class to convert PokerKit actions into human-readable text."""

class ActionConverter:
    """Utility class to convert PokerKit actions into human-readable text."""
    
    @staticmethod
    def to_human_readable(action) -> str:
        """Convert a PokerKit action to human-readable text."""
        if action is None:
            return None
            
        action_type = type(action).__name__
        
        # Handle different action types (including mock classes for testing)
        if action_type in ['Folding', 'MockFolding']:
            return f"Player {action.player_index} folds"
            
        elif action_type in ['CheckingOrCalling', 'MockCheckingOrCalling']:
            if hasattr(action, 'amount') and action.amount > 0:
                return f"Player {action.player_index} calls {action.amount}"
            else:
                return f"Player {action.player_index} checks"
                
        elif action_type in ['CompletionBettingOrRaisingTo', 'MockCompletionBettingOrRaisingTo']:
            return f"Player {action.player_index} raises to {action.amount}"
            
        elif action_type in ['BoardDealing', 'MockBoardDealing']:
            cards_str = ', '.join(str(card) for card in action.cards)
            return f"Board dealt: {cards_str}"
            
        elif action_type in ['HoleDealing', 'MockHoleDealing']:
            return f"Player {action.player_index} dealt hole cards"
            
        elif action_type in ['BlindOrStraddlePosting', 'MockBlindOrStraddlePosting']:
            return f"Player {action.player_index} posts blind: {action.amount}"
            
        elif action_type in ['AntePosting', 'MockAntePosting']:
            return f"Player {action.player_index} posts ante: {action.amount}"
            
        elif action_type in ['ChipsPulling', 'MockChipsPulling']:
            return f"Player {action.player_index} pulls chips: {action.amount}"
            
        elif action_type in ['ChipsPushing', 'MockChipsPushing']:
            # Handle chips pushing to show who won the hand
            if hasattr(action, 'amounts') and action.amounts:
                winners = []
                for i, amount in enumerate(action.amounts):
                    if amount > 0:
                        winners.append(f"Player {i} wins {amount}")
                
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
            return f"Player {action.player_index} mucks hand"
            
        elif action_type in ['CardBurning', 'MockCardBurning']:
            return "Card burned"
            
        else:
            # Fallback for unknown action types
            if hasattr(action, 'player_index') and hasattr(action, 'amount'):
                return f"{action_type}: Player {action.player_index}, Amount {action.amount}"
            elif hasattr(action, 'player_index'):
                return f"{action_type}: Player {action.player_index}"
            else:
                return f"{action_type}" 