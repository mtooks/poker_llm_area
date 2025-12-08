# React Visualization Plan for Poker LLM Arena

## Overview
Create a React-based web interface to visualize poker hands in real-time as they're being played by LLM players.

## Architecture

### Backend Integration
- **WebSocket Server** (Flask-SocketIO or FastAPI WebSocket)
  - Stream game state updates in real-time
  - Emit events for each action, board card, street change
  - Send hand completion events with results

### Frontend Structure

```
src/
├── components/
│   ├── GameTable/
│   │   ├── GameTable.jsx          # Main table container
│   │   ├── PlayerSeat.jsx         # Individual player component
│   │   ├── Board.jsx              # Community cards display
│   │   ├── Pot.jsx                # Pot size display
│   │   └── DealerButton.jsx       # Dealer button indicator
│   ├── ActionHistory/
│   │   ├── ActionHistory.jsx      # Scrollable action log
│   │   └── ActionItem.jsx         # Individual action display
│   ├── HandVisualization/
│   │   ├── HandVisualization.jsx  # Main hand view
│   │   ├── StreetIndicator.jsx    # Pre-flop/Flop/Turn/River
│   │   └── BettingRound.jsx       # Current betting round info
│   ├── PlayerInfo/
│   │   ├── PlayerCard.jsx         # Player stats card
│   │   ├── StackDisplay.jsx       # Chip count
│   │   └── HoleCards.jsx          # Player's cards (hidden/shown)
│   ├── GameControls/
│   │   ├── StartGame.jsx          # Start new game
│   │   ├── PauseResume.jsx        # Pause/resume game
│   │   └── SpeedControl.jsx       # Animation speed
│   └── Layout/
│       ├── Header.jsx
│       └── Sidebar.jsx
├── hooks/
│   ├── useWebSocket.js            # WebSocket connection hook
│   ├── useGameState.js            # Game state management
│   └── useHandAnimation.js        # Animation timing
├── utils/
│   ├── cardUtils.js               # Card rendering, emoji conversion
│   ├── pokerUtils.js              # Hand evaluation, formatting
│   └── actionParser.js            # Parse action strings
├── App.jsx
└── index.jsx
```

## Component Breakdown

### 1. GameTable Component
**Purpose**: Main visual representation of the poker table

**Props/State**:
```javascript
{
  players: [
    {
      name: string,
      stack: number,
      position: "Button" | "Small Blind" | "Big Blind" | "UTG" | etc,
      holeCards: [Card, Card] | null,  // null if not revealed
      isActive: boolean,  // currently acting
      isFolded: boolean,
      currentBet: number,
      isAllIn: boolean
    }
  ],
  board: [Card],  // Community cards
  pot: number,
  currentStreet: "Pre-flop" | "Flop" | "Turn" | "River",
  dealerPosition: number
}
```

**Visual Layout**:
- Circular or oval table
- Player seats arranged around table
- Center: board cards, pot, dealer button
- Highlight active player
- Show betting amounts per player

### 2. PlayerSeat Component
**Purpose**: Individual player visualization

**Displays**:
- Player name
- Stack size (chips)
- Position badge (Button, BB, etc.)
- Hole cards (face down or face up)
- Current bet amount
- Folded/All-in indicators
- Active player highlight (glow/border)

**Animations**:
- Card flip when revealed
- Chip stack animation on bet
- Highlight pulse when it's their turn

### 3. Board Component
**Purpose**: Community cards display

**Features**:
- Show cards as they're dealt (Flop: 3, Turn: +1, River: +1)
- Card reveal animation
- Street labels (Flop, Turn, River)
- Pot size display above/below board

### 4. ActionHistory Component
**Purpose**: Scrollable log of all actions

**Data Structure**:
```javascript
{
  timestamp: number,
  player: string,
  action: "fold" | "check" | "call" | "raise_to: X",
  amount: number | null,
  commentary: string | null,  // LLM reasoning
  street: string
}
```

**Features**:
- Auto-scroll to latest action
- Color coding by action type
- Expandable commentary
- Filter by player/street

### 5. HandVisualization Component
**Purpose**: Main container orchestrating hand display

**State Management**:
```javascript
const [handState, setHandState] = useState({
  handId: number,
  status: "waiting" | "active" | "complete",
  currentStreet: string,
  board: [],
  players: [],
  pot: 0,
  actions: [],
  isPaused: boolean
});
```

**Real-time Updates**:
- Listen to WebSocket events
- Update state incrementally
- Trigger animations on state changes

## Data Flow

### WebSocket Event Types

```javascript
// Hand start
{
  type: "hand_start",
  data: {
    handId: number,
    players: [...],
    dealerPosition: number,
    holeCards: { [playerIndex]: [Card, Card] }  // All cards for visualization
  }
}

// Action taken
{
  type: "action",
  data: {
    player: string,
    playerIndex: number,
    action: string,
    amount: number | null,
    commentary: string | null,
    newStack: number,
    pot: number
  }
}

// Board card dealt
{
  type: "board_card",
  data: {
    street: "flop" | "turn" | "river",
    card: Card,
    board: [Card]  // Full board after this card
  }
}

// Street change
{
  type: "street_change",
  data: {
    street: "Pre-flop" | "Flop" | "Turn" | "River",
    board: [Card]
  }
}

// Hand complete
{
  type: "hand_complete",
  data: {
    winners: [playerIndex],
    finalStacks: [number],
    showdown: {
      [playerIndex]: {
        holeCards: [Card],
        handRank: string,
        profit: number
      }
    }
  }
}
```

## State Management Strategy

### Option 1: React Context + useReducer
```javascript
// GameContext.jsx
const GameStateContext = createContext();

function gameReducer(state, action) {
  switch (action.type) {
    case 'HAND_START':
      return { ...state, currentHand: action.payload };
    case 'ACTION_TAKEN':
      return {
        ...state,
        actions: [...state.actions, action.payload],
        players: updatePlayerState(state.players, action.payload)
      };
    case 'BOARD_UPDATE':
      return { ...state, board: action.payload };
    // ... more cases
  }
}
```

### Option 2: Zustand (simpler state management)
```javascript
// store.js
import create from 'zustand';

const useGameStore = create((set) => ({
  currentHand: null,
  players: [],
  board: [],
  actions: [],
  addAction: (action) => set((state) => ({
    actions: [...state.actions, action]
  })),
  updateBoard: (cards) => set({ board: cards }),
  // ... more actions
}));
```

## Real-time Updates Hook

```javascript
// useWebSocket.js
function useWebSocket(url) {
  const [socket, setSocket] = useState(null);
  const [gameState, setGameState] = useState(null);
  
  useEffect(() => {
    const ws = new WebSocket(url);
    
    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      
      switch (message.type) {
        case 'hand_start':
          setGameState(initializeHand(message.data));
          break;
        case 'action':
          setGameState(prev => addAction(prev, message.data));
          break;
        // ... handle other events
      }
    };
    
    setSocket(ws);
    return () => ws.close();
  }, [url]);
  
  return { socket, gameState };
}
```

## Card Visualization

### Card Component
```javascript
// Card.jsx
function Card({ card, faceUp = false, size = "medium" }) {
  // card format: "As" (Ace of spades) or "Kh" (King of hearts)
  const [rank, suit] = parseCard(card);
  const suitEmoji = { 'S': '♠️', 'H': '♥️', 'D': '♦️', 'C': '♣️' };
  const suitColor = ['H', 'D'].includes(suit) ? 'red' : 'black';
  
  return (
    <div className={`card ${faceUp ? 'face-up' : 'face-down'}`}>
      {faceUp ? (
        <>
          <span className="rank">{rank}</span>
          <span className="suit" style={{ color: suitColor }}>
            {suitEmoji[suit]}
          </span>
        </>
      ) : (
        <div className="card-back">🂠</div>
      )}
    </div>
  );
}
```

## Animation Strategy

### 1. Action Animations
- **Bet/Raise**: Slide chips from player to pot
- **Fold**: Fade out player cards
- **Card Deal**: Flip animation with delay
- **Street Change**: Fade transition

### 2. Timing Controls
```javascript
const [animationSpeed, setAnimationSpeed] = useState(1.0); // 1x, 2x, 0.5x

// Use CSS animations with dynamic duration
<div 
  className="action-animation"
  style={{ animationDuration: `${baseDuration / animationSpeed}s` }}
>
```

### 3. Pause/Resume
- Pause WebSocket processing
- Queue events while paused
- Resume with queued events

## Backend Modifications Needed

### In main.py `_play_hand` method:

```python
# After each action
await emit_game_event("action", {
    "player": player_name,
    "playerIndex": actual_player_idx,
    "action": decision.token,
    "commentary": decision.commentary,
    "newStack": st.stacks[plr_idx],
    "pot": st.total_pot_amount,
    "street": street_name
})

# When board updates
if board != last_board:
    await emit_game_event("board_card", {
        "street": street_name.lower(),
        "card": str(new_card),
        "board": [str(c) for c in board]
    })

# Hand start
await emit_game_event("hand_start", {
    "handId": hand_no,
    "players": player_data,
    "dealerPosition": self.dealer_position,
    "holeCards": {i: [str(c) for c in cards] for i, cards in hand_data["hole_cards"].items()}
})
```

## Styling Approach

### CSS-in-JS (styled-components) or Tailwind CSS
- Modern, responsive design
- Dark theme (poker table aesthetic)
- Smooth animations
- Mobile-friendly layout

### Color Scheme
- Table: Green felt (#0d5d2f)
- Cards: White with black/red text
- Chips: Color-coded by value
- Active player: Gold/yellow highlight

## Additional Features

### 1. Hand Replay
- Store complete hand data
- Replay button to watch hand again
- Step through actions one-by-one

### 2. Statistics Panel
- Win rates per player
- VPIP, PFR stats
- Hand history summary

### 3. Player Commentary
- Expandable LLM reasoning
- Show/hide commentary toggle
- Highlight interesting decisions

### 4. Multi-hand View
- Show multiple hands in tabs
- Compare different game runs

## Implementation Phases

### Phase 1: Basic Visualization
- Static table with players
- Card components
- Basic action log
- WebSocket connection

### Phase 2: Real-time Updates
- Live action streaming
- Board card reveals
- Stack updates

### Phase 3: Animations
- Card flip animations
- Chip animations
- Smooth transitions

### Phase 4: Advanced Features
- Hand replay
- Statistics
- Commentary display
- Speed controls

## Technology Stack

- **React** 18+ (with hooks)
- **WebSocket**: Native WebSocket API or Socket.IO client
- **State Management**: Zustand or React Context
- **Styling**: Tailwind CSS or styled-components
- **Animations**: Framer Motion or CSS transitions
- **Build Tool**: Vite (fast, modern)

## Example Component Structure

```jsx
// App.jsx
function App() {
  const { gameState, isConnected } = useWebSocket('ws://localhost:5000');
  const [speed, setSpeed] = useState(1.0);
  
  return (
    <div className="app">
      <Header />
      <div className="main-content">
        <GameTable 
          players={gameState?.players || []}
          board={gameState?.board || []}
          pot={gameState?.pot || 0}
          currentStreet={gameState?.currentStreet}
        />
        <Sidebar>
          <ActionHistory actions={gameState?.actions || []} />
          <GameControls 
            speed={speed} 
            onSpeedChange={setSpeed}
          />
        </Sidebar>
      </div>
    </div>
  );
}
```

This plan provides a solid foundation for building a React-based visualization system that can display poker hands in real-time as they're played by LLM players.


