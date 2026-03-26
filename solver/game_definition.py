"""Define the abstracted NLHE game for OpenSpiel's universal_poker."""

import pyspiel

# Simplified heads-up NLHE game definition.
# Uses a small number of discrete bet sizes to keep the game tree tractable
# for tabular CFR.  Full NLHE has continuous bet sizes (intractable).
#
# Key abstraction choices:
#   - 2 players (heads-up only)
#   - 4 betting rounds (preflop, flop, turn, river)
#   - Fixed 500-chip stacks (250 BB at 1/2 blinds)
#   - Bet sizes limited by OpenSpiel's universal_poker action space

# GAMEDEF kept for documentation / reference.
GAMEDEF = """\
GAMEDEF
nolimit
numPlayers = 2
numRounds = 4
stack = 500 500
blind = 1 2
firstPlayer = 2 1 1 1
numSuits = 4
numRanks = 13
numHoleCards = 2
numBoardCards = 0 3 1 1
END GAMEDEF
"""

# Parameters dict used to load the game in OpenSpiel.
GAME_PARAMS = {
    "betting": "nolimit",
    "numPlayers": 2,
    "numRounds": 4,
    "stack": "500 500",
    "blind": "1 2",
    "firstPlayer": "2 1 1 1",
    "numSuits": 4,
    "numRanks": 13,
    "numHoleCards": 2,
    "numBoardCards": "0 3 1 1",
}


def load_game():
    """Load and return the abstracted NLHE OpenSpiel game object."""
    return pyspiel.load_game("universal_poker", GAME_PARAMS)
