# Plan: GTO Player via OpenSpiel CFR Solver

## Goal
Replace the current heuristic-based `GTOPlayer` with a true GTO player that uses precomputed Nash equilibrium strategies from OpenSpiel's CFR solver. This gives a rigorous benchmark for comparing LLM poker performance.

## Why OpenSpiel?
- Open-source (Apache 2.0), maintained by Google DeepMind
- Has `universal_poker` game supporting configurable NLHE via ACPC GAMEDEF format
- Ships CFR and CFR+ solvers with Python bindings
- `pip install open-spiel` (no build-from-source needed on macOS ARM64 / Linux)

## The Core Problem

Full No-Limit Hold'em has ~10^165 game tree nodes. Tabular CFR can handle ~10^12. You **cannot** solve full NLHE directly. The solution is **abstraction**: reduce the game to a tractable size, solve the abstract game, then map real game states back to abstract states at play time.

---

## Architecture

```
                    OFFLINE (one-time)                          ONLINE (per decision)
              ┌─────────────────────────┐              ┌──────────────────────────────┐
              │  1. Define abstracted    │              │  5. Receive PokerKit game     │
              │     NLHE via GAMEDEF     │              │     state (JSON dict)         │
              │                          │              │                               │
              │  2. Run CFR+ solver      │              │  6. TRANSLATE: PokerKit state │
              │     for N iterations     │              │     → OpenSpiel info state    │
              │                          │              │     (cards, actions, history)  │
              │  3. Extract average      │              │                               │
              │     policy (Nash approx) │              │  7. Map hole cards + board    │
              │                          │              │     to abstract bucket        │
              │  4. Serialize policy     │              │                               │
              │     to disk (.pkl)       │              │  8. Look up info state in     │
              └─────────────────────────┘              │     precomputed policy        │
                                                        │                               │
                                                        │  9. Sample action from         │
                                                        │     strategy distribution     │
                                                        │                               │
                                                        │ 10. TRANSLATE: abstract action │
                                                        │     → PokerKit legal action   │
                                                        └──────────────────────────────┘
```

---

## Step-by-Step Implementation

### Step 1: Install and validate OpenSpiel
**File:** `requirements.txt`

```
open-spiel>=1.6.0
```

Write a small smoke test that loads `universal_poker` with a GAMEDEF string and plays a random game to completion. This validates the install works.

**Estimated effort:** 30 min

---

### Step 2: Define the abstracted NLHE game
**New file:** `solver/game_definition.py`

Define a simplified but representative NLHE game via GAMEDEF:

```python
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
```

**Key abstraction decisions:**

| Dimension | Full NLHE | Our Abstraction | Impact |
|-----------|-----------|-----------------|--------|
| Bet sizes | Continuous (any amount) | Discrete: fold, check/call, 0.5x pot, 1x pot, all-in | Biggest reduction. Limits expressiveness but captures key strategic sizes. |
| Card buckets | 1,326 preflop combos, millions postflop | Preflop: no abstraction (1,326 is tractable). Postflop: cluster by hand equity into ~200 buckets per street | Major reduction. Loses some board-texture nuance. |
| Stack depth | Variable | Fixed at 250bb (matches arena's 1000 stack / 2bb big blind setup, roughly) | Minor simplification. |
| Players | 2-6 | 2 (heads-up) | Massive reduction. Multi-way pots not covered — see Limitations. |

**Bet abstraction** is handled by OpenSpiel's `universal_poker` action space. The game natively limits actions to a set of discrete bet sizes. We configure this in the GAMEDEF or via game parameters.

**Card abstraction** must be built manually (OpenSpiel doesn't include it). See Step 3.

**Estimated effort:** 1-2 hours

---

### Step 3: Build PokerKit ↔ OpenSpiel translation layer
**New file:** `solver/format_translator.py`

The arena runs on PokerKit. The solver runs on OpenSpiel's ACPC format. These two systems represent cards, actions, and game state differently. This step builds the bridge between them.

#### 3a. Card translation (trivial)

Both use the same `"As"`, `"Kh"` format. No conversion needed — cards pass through as-is.

#### 3b. Action translation (significant work)

**Arena → Abstract (inbound):** Parse the arena's betting history to reconstruct an abstract action sequence the solver understands.

| Arena format | OpenSpiel ACPC format | Notes |
|---|---|---|
| `"fold"` | `f` | Direct map |
| `"check"` | `c` | Direct map |
| `"call"` | `c` | ACPC uses `c` for both check and call |
| `"raise_to: 400"` | `r400` | Both use absolute amounts, just different string format |
| Street separator (implicit via `"Current Street"`) | `/` in action string | ACPC uses `/` to delimit betting rounds |

**Abstract → Arena (outbound):** Convert the solver's chosen abstract action back to a legal arena action.

```python
class FormatTranslator:
    # Abstract bet sizes as fractions of pot
    ABSTRACT_SIZES = [0.33, 0.67, 1.0, float('inf')]  # inf = all-in

    def arena_history_to_acpc(self, history: list[str], street_boundaries: list[int]) -> str:
        """
        Convert:  ["Player 1 posts blind: 1", "Player 2 posts blind: 2",
                   "Player 1 raises to 6", "Player 2 calls 4"]
        To:       "r6c"  (preflop action only, blinds are implicit in GAMEDEF)
        """
        acpc_actions = []
        for entry in history:
            if "posts blind" in entry or "posts ante" in entry:
                continue  # Blinds/antes are implicit in GAMEDEF
            if "folds" in entry:
                acpc_actions.append("f")
            elif "checks" in entry or "calls" in entry:
                acpc_actions.append("c")
            elif "raises to" in entry:
                amount = parse_amount(entry)
                acpc_actions.append(f"r{amount}")
        # Insert '/' at street boundaries
        return insert_street_separators(acpc_actions, street_boundaries)

    def snap_to_abstract_bet(self, actual_bet: int, pot: int) -> str:
        """
        LLM bets 73% pot but our abstraction only has {33%, 67%, 100%, all-in}.
        Snap to nearest: 67% pot.
        """
        if pot == 0:
            return f"r{actual_bet}"
        ratio = actual_bet / pot
        nearest = min(self.ABSTRACT_SIZES, key=lambda x: abs(x - ratio))
        if nearest == float('inf'):
            return "all-in"
        abstract_amount = int(pot * nearest)
        return f"r{abstract_amount}"

    def abstract_action_to_arena(self, action: str, legal_actions: list[str],
                                  pot: int, stack: int) -> str:
        """
        Convert solver output back to arena format.
        "r{amount}" → "raise_to: {clamped_amount}" (clamped to legal min/max)
        "c"         → "call" or "check" (based on what's legal)
        "f"         → "fold"
        """
        if action == "f":
            return "fold"
        if action == "c":
            return "check" if "check" in legal_actions else "call"
        if action.startswith("r"):
            target = int(action[1:])
            min_raise, max_raise = parse_raise_bounds(legal_actions)
            clamped = max(min_raise, min(target, max_raise or stack))
            return f"raise_to: {clamped}"
```

#### 3c. Game state translation (the core challenge)

The arena sends players a JSON dict. The solver uses OpenSpiel info state strings. We need to map between them.

**Arena JSON state:**
```json
{
  "Current Street": "Flop",
  "Hole Cards": ["As", "Kh"],
  "board": ["7d", "2c", "Ah"],
  "Pot size": 300,
  "Your stack": 850,
  "to_call": 100,
  "min_raise_to": 200,
  "history": ["Player 1 posts blind: 1", "Player 2 posts blind: 2",
              "Player 1 raises to 6", "Player 2 calls 4",
              "Board dealt: 7d, 2c, Ah",
              "Player 2 bets 100"]
}
```

**OpenSpiel info state string (what the solver indexes on):**
```
"[Round 1][Player: 0][Ah][Kd][Board: 7d2cAh][Bets: r6c/r100]"
```

**Translation steps:**
1. Extract hole cards and board from JSON (already in compatible card format)
2. Parse `history` list to reconstruct the ACPC action sequence, skipping blinds/antes/deals
3. Map each concrete bet to nearest abstract bet size (this is where precision is lost)
4. Combine card bucket (from Step 4) + abstract action sequence into a lookup key
5. Handle **off-tree states**: when the opponent's action sequence doesn't match any path in the solved game tree (e.g., a bet size we never abstracted), find the closest matching node

#### 3d. Off-tree handling

This is the trickiest edge case. When an LLM bets an amount that doesn't exist in our abstraction, the resulting game tree path may not exist in the precomputed policy.

**Strategy:** Snap to the nearest abstract bet size for lookup purposes, but use the actual bet size when computing pot odds for our response. This means:
- The *frequency* of our response (how often we call/raise/fold) comes from the solver
- The *sizing* of our response is adjusted to the real pot/stack geometry

```python
def handle_off_tree(self, actual_history, abstract_history, policy):
    """When actual game diverges from abstract tree, find closest node."""
    # Try exact match first
    if abstract_history in policy:
        return policy[abstract_history]

    # Snap last action to nearest abstract size and retry
    snapped = self.snap_last_action(abstract_history)
    if snapped in policy:
        return policy[snapped]

    # Fallback: use default strategy (e.g., pot-odds based)
    return self.default_strategy()
```

**Estimated effort:** 1.5 days

---

### Step 4: Build card abstraction (bucketing)
**New file:** `solver/card_abstraction.py`
*(was Step 3 before translation layer was added)*

Map each possible hand+board combination to an abstract "bucket" so the solver sees a tractable number of information states.

**Approach: Equity-based clustering**

1. **Preflop (169 strategic hands):** No abstraction needed. There are only 169 strategically distinct preflop hands (accounting for suit symmetry). This is small enough for tabular CFR.

2. **Flop / Turn / River:**
   - For each possible hand+board combo, estimate equity via Monte Carlo rollout (deal remaining cards 1,000x, evaluate winner)
   - Use k-means clustering to group hands into buckets by equity
   - Bucket counts: ~200 flop, ~200 turn, ~200 river
   - Store bucket assignments as a lookup table (dict or numpy array)

**Dependencies:** Need a fast hand evaluator. Options:
- `treys` (pure Python, MIT license, `pip install treys`) — fast enough for offline precomputation
- `phevaluator` (C extension, faster) — if treys is too slow

**This is the most complex step.** The offline equity calculation + clustering is computationally expensive (hours of CPU time) but only needs to run once. Results are cached to disk.

```python
# Pseudocode
def compute_flop_buckets(n_buckets=200, n_rollouts=1000):
    equities = {}
    for hand in all_preflop_hands():        # 1,326 combos
        for flop in all_flops(exclude=hand):  # ~19,600 flops
            equity = monte_carlo_equity(hand, flop, n_rollouts)
            equities[(hand, flop)] = equity

    # Cluster into buckets
    labels = kmeans(list(equities.values()), n_clusters=n_buckets)
    return {key: label for key, label in zip(equities.keys(), labels)}
```

**Estimated effort:** 1-2 days (including testing and performance tuning)

---

### Step 5: Run CFR+ solver offline
**New file:** `solver/solve.py`

```python
import pyspiel
from open_spiel.python.algorithms import cfr

game = pyspiel.load_game("universal_poker", {
    "gamedef": pyspiel.GameParameter(GAMEDEF)
})

solver = cfr.CFRPlusSolver(game)

for i in range(100_000):  # More iterations = closer to Nash
    solver.evaluate_and_update_policy()
    if i % 10_000 == 0:
        policy = solver.average_policy()
        # Optionally measure exploitability (expensive for large games)
        print(f"Iteration {i} complete")

# Save the converged policy
policy = solver.average_policy()
save_policy(policy, "solver/policy.pkl")
```

**Key considerations:**
- CFR+ converges faster than vanilla CFR
- With our abstractions (~200 buckets x 4 streets x discrete bet sizes), the game tree should be in the millions of info states — solvable in minutes to hours depending on hardware
- Memory: each info state stores a probability distribution over actions. With ~5M info states and ~5 actions each, that's ~200MB of floats. Feasible.
- We can measure convergence via exploitability (how much a perfect adversary could exploit the strategy). Target: <0.5bb/100 hands.

**Estimated effort:** 1 day (mostly waiting for solver to converge + tuning iteration count)

---

### Step 6: Build the state mapper (ties it all together)
**New file:** `solver/state_mapper.py`

This orchestrates the translation layer (Step 3) and card abstraction (Step 4) to go from arena state → policy lookup → arena action.

```python
class StateMapper:
    def __init__(self, policy, card_buckets, translator):
        self.policy = policy              # Precomputed Nash strategy
        self.card_buckets = card_buckets  # Hand+board -> bucket mapping
        self.translator = translator      # FormatTranslator from Step 3

    def get_strategy(self, hole_cards, board, street, pot, stack, history, legal_actions):
        """Return action probability distribution for this game state."""
        # Step 3: Translate arena history → abstract ACPC action sequence
        acpc_history = self.translator.arena_history_to_acpc(history)
        abstract_history = self.translator.snap_all_bets_to_abstract(acpc_history, pot)

        # Step 4: Map cards to equity bucket
        bucket = self.card_buckets.get_bucket(hole_cards, board, street)

        # Combine into solver lookup key
        info_state = self._build_info_state_key(bucket, abstract_history)

        # Look up (with off-tree fallback)
        return self.translator.handle_off_tree(acpc_history, info_state, self.policy)

    def choose_arena_action(self, strategy, legal_actions, pot, stack):
        """Sample from strategy distribution, return arena-formatted action."""
        abstract_action = random.choices(
            list(strategy.keys()),
            weights=list(strategy.values())
        )[0]
        return self.translator.abstract_action_to_arena(abstract_action, legal_actions, pot, stack)
```

**Estimated effort:** 0.5 days

---

### Step 7: Implement the new CFR-GTO Player
**Modified file:** `players/gto_player.py` (or new `players/cfr_gto_player.py`)

```python
class CFRGTOPlayer(BasePlayer):
    """GTO player backed by precomputed CFR+ Nash equilibrium strategy."""

    def __init__(self, name, model="cfr-gto", policy_path="solver/policy.pkl", ...):
        super().__init__(name=name, model=model, ...)
        self.mapper = StateMapper(
            policy=load_policy(policy_path),
            card_buckets=load_buckets("solver/buckets.pkl")
        )

    async def _chat(self, messages):
        state, legal = self._extract_state_and_legal(messages)

        # Get Nash strategy for this spot
        strategy = self.mapper.get_strategy(
            hole_cards=state["Hole Cards"],
            board=state["board"],
            street=state["Current Street"],
            pot=state["Pot size"],
            stack=state["Your stack"],
            betting_history=state.get("betting_history", [])
        )

        # Sample action from the strategy distribution (mixed strategy)
        action = random.choices(
            list(strategy.keys()),
            weights=list(strategy.values())
        )[0]

        # Map abstract action back to concrete bet size
        concrete_action = self._to_concrete_action(action, legal, state)
        return f"{concrete_action}@GTO equilibrium play"
```

**Key difference from current GTOPlayer:** Instead of computing a single scalar strength and using fixed thresholds, this player looks up the equilibrium mixed strategy and **samples** from it. This means it will sometimes bluff, sometimes check-raise, sometimes fold strong hands — all at theoretically correct frequencies.

**Estimated effort:** 0.5 days

---

### Step 8: Register in player factory
**Modified file:** `players/player_factory.py`

Add `"cfr-gto"` as a new provider option. Update `game_config.py` to allow selecting it.

**Estimated effort:** 30 min

---

### Step 9: Precompute and cache everything
**New file:** `solver/precompute.py`

A single script that runs the full offline pipeline:
1. Compute card abstraction buckets (equity clustering)
2. Define abstract NLHE game
3. Run CFR+ for N iterations
4. Save policy + buckets to `solver/data/`

Add a check in `CFRGTOPlayer.__init__` that raises a clear error if precomputed data doesn't exist, with instructions to run `python solver/precompute.py`.

**Estimated effort:** 1 hour

---

### Step 10: Validate solver — unit tests with Kuhn/Leduc exact equilibria
**New file:** `tests/test_solver_convergence.py`

Before trusting the solver on NLHE, prove it converges correctly on games with known analytical solutions.

**Kuhn poker (3-card, 2-player):**
- Nash equilibrium is analytically known (parameterized by alpha in [0, 1/3])
- Game value = -1/18 per hand for Player 1
- OpenSpiel ships hardcoded expected values in `exploitability_test.py`:
  - Uniform random policy → NashConv = 11/12 (~0.9167)
  - Nash equilibrium → NashConv = 0.0

**Leduc poker (6-card, 2-player):**
- Uniform random policy → NashConv = 4.7472222...

```python
import pyspiel
from open_spiel.python.algorithms import cfr, exploitability

def test_kuhn_convergence():
    game = pyspiel.load_game("kuhn_poker")
    solver = cfr.CFRPlusSolver(game)

    for _ in range(10_000):
        solver.evaluate_and_update_policy()

    policy = solver.average_policy()
    exploit = exploitability.exploitability(game, policy)
    assert exploit < 1e-4, f"Kuhn exploitability {exploit} too high (expected ~0)"

def test_leduc_convergence():
    game = pyspiel.load_game("leduc_poker")
    solver = cfr.CFRPlusSolver(game)

    for _ in range(10_000):
        solver.evaluate_and_update_policy()

    policy = solver.average_policy()
    exploit = exploitability.exploitability(game, policy)
    assert exploit < 0.05, f"Leduc exploitability {exploit} too high"

def test_abstracted_nlhe_convergence():
    """Run CFR+ on our abstracted NLHE game and verify exploitability decreases."""
    game = pyspiel.load_game("universal_poker", {"gamedef": pyspiel.GameParameter(GAMEDEF)})
    solver = cfr.CFRPlusSolver(game)

    prev_exploit = float('inf')
    for i in range(50_000):
        solver.evaluate_and_update_policy()
        if i % 10_000 == 0:
            policy = solver.average_policy()
            exploit = exploitability.exploitability(game, policy)
            assert exploit < prev_exploit, "Exploitability not decreasing"
            prev_exploit = exploit

    # Final exploitability should be small relative to the game
    assert prev_exploit < 0.5, f"Abstracted NLHE exploitability {prev_exploit} too high"
```

**What this proves:** The CFR+ solver implementation converges to Nash equilibrium. If these tests fail, nothing downstream can be trusted.

**Estimated effort:** 0.5 days

---

### Step 11: Validate decisions — spot-check against PokerBench dataset
**New file:** `tests/test_pokerbench_accuracy.py`

PokerBench (HuggingFace: `RZ412/PokerBench`) contains 11,000 NLHE test scenarios with solver-computed optimal actions. Each record has a game state and a `correct_decision` field (fold/check/call/bet with sizing).

**Setup:**
```bash
pip install datasets  # HuggingFace datasets library
```

```python
from datasets import load_dataset

# Load the test splits
preflop_test = load_dataset("RZ412/PokerBench", data_files="preflop_1k_test_set_*.csv")
postflop_test = load_dataset("RZ412/PokerBench", data_files="postflop_10k_test_set_*.csv")
```

**Validation approach:**

1. Parse each PokerBench scenario into the same JSON state format our arena uses
2. Feed it to `CFRGTOPlayer._chat()` and capture the chosen action
3. Compare against `correct_decision`
4. Score as: exact match, directionally correct (same action type, different sizing), or wrong

```python
def test_pokerbench_preflop(cfr_player, preflop_test):
    exact = directional = wrong = 0
    for scenario in preflop_test:
        state = parse_pokerbench_to_arena_state(scenario)
        our_action = cfr_player.decide(state)
        reference = scenario["correct_decision"]

        if actions_match_exactly(our_action, reference):
            exact += 1
        elif same_action_type(our_action, reference):
            directional += 1
        else:
            wrong += 1

    accuracy = exact / len(preflop_test)
    directional_accuracy = (exact + directional) / len(preflop_test)
    print(f"Exact match: {accuracy:.1%}")
    print(f"Directional match: {directional_accuracy:.1%}")

    # We expect ~70-85% directional accuracy given our abstraction level
    assert directional_accuracy > 0.60, f"Accuracy {directional_accuracy:.1%} too low"
```

**Important caveats:**
- PokerBench is 6-max; our solver is heads-up. Preflop ranges will differ — filter to heads-up spots or accept lower accuracy on multi-way scenarios.
- Bet sizing won't match exactly due to our abstraction (we have discrete sizes, PokerBench has continuous). Score action *type* (raise vs call vs fold) separately from sizing accuracy.
- PokerBench ground truth comes from GTOWizard/WASM-Postflop solvers. Differences may reflect abstraction choices, not errors.

**What this proves:** Our CFR player makes decisions that are directionally consistent with production-grade GTO solvers across a large sample of real scenarios.

**Estimated effort:** 1 day (mostly building the PokerBench→arena state parser)

---

### Step 12: Validate strategy — live benchmark against Slumbot API
**New file:** `tests/test_slumbot_benchmark.py`

Slumbot is a near-GTO heads-up NLHE bot (2018 ACPC champion) with a free REST API. A correctly implemented GTO player should break roughly even against it.

**API:**
- `POST https://slumbot.com/api/new_hand` → returns hand state + token
- `POST https://slumbot.com/api/act` → submit action, get next state
- Action format: `k` (check), `c` (call), `f` (fold), `b{amount}` (bet)
- 200bb deep, blinds 50/100

```python
import requests

class SlumbotBenchmark:
    BASE = "https://slumbot.com/api"

    def play_hand(self, cfr_player):
        """Play one hand against Slumbot, return profit/loss."""
        resp = requests.post(f"{self.BASE}/new_hand").json()
        token = resp["token"]

        while not resp.get("is_terminal"):
            if its_our_turn(resp):
                # Translate Slumbot state → arena state → get CFR decision
                arena_state = self.slumbot_to_arena_state(resp)
                action = cfr_player.decide(arena_state)
                slumbot_action = self.arena_to_slumbot_action(action)
                resp = requests.post(f"{self.BASE}/act",
                    json={"token": token, "incr": slumbot_action}).json()
            else:
                # Slumbot already acted, state updated
                pass

        return resp.get("winnings", 0)  # In chips (positive = we won)

    def run_benchmark(self, cfr_player, n_hands=10_000):
        total_profit = 0
        for i in range(n_hands):
            profit = self.play_hand(cfr_player)
            total_profit += profit
            if i % 1000 == 0:
                bb_per_100 = (total_profit / (i + 1)) * 100 / 100  # Normalize to bb/100
                print(f"Hand {i}: {bb_per_100:.1f} bb/100")

        bb_per_100 = (total_profit / n_hands) * 100 / 100
        print(f"Final: {bb_per_100:.1f} bb/100 over {n_hands} hands")

        # A GTO-approximate bot should be within ±5 bb/100 of breakeven
        # over 10K hands (variance is still significant at this sample size)
        assert abs(bb_per_100) < 10, f"Win rate {bb_per_100:.1f} bb/100 is too far from breakeven"
```

**Translation needed:** Slumbot uses its own state format (different from both PokerKit and OpenSpiel). Need a small adapter:
- Slumbot cards: same `"As"` format (compatible)
- Slumbot actions: `k`/`c`/`f`/`b{amount}` → translate to/from arena format
- Slumbot betting: absolute chip amounts, 200bb stacks, 50/100 blinds

**What this proves:** The full pipeline works end-to-end against a real near-GTO opponent, and the strategy is not wildly exploitable. This is the ultimate integration test.

**Note:** Rate-limit your requests (Slumbot's API is free but has no SLA). Add 100ms delay between hands. 10K hands ≈ 20 minutes.

**Estimated effort:** 1 day (mostly building the Slumbot↔arena translator)

---

## New Files Summary

```
solver/
├── __init__.py
├── game_definition.py      # GAMEDEF string + game config
├── format_translator.py    # PokerKit ↔ OpenSpiel/ACPC format translation
├── card_abstraction.py     # Equity bucketing via Monte Carlo + k-means
├── solve.py                # CFR+ solver runner
├── state_mapper.py         # Orchestrates translation + bucketing + policy lookup
├── precompute.py           # One-shot offline pipeline
└── data/                   # Cached precomputed artifacts
    ├── policy.pkl
    └── buckets.pkl

players/
├── cfr_gto_player.py       # New player using precomputed CFR strategy

tests/
├── test_solver_convergence.py  # Step 10: Kuhn/Leduc exact equilibria tests
├── test_pokerbench_accuracy.py # Step 11: Spot-check vs PokerBench 11K test set
├── test_slumbot_benchmark.py   # Step 12: Live benchmark vs Slumbot API
```

**Modified files:**
- `players/player_factory.py` — add cfr-gto provider
- `game_config.py` — add cfr-gto player option
- `requirements.txt` — add `open-spiel`, `treys`, `datasets` (HuggingFace)

---

## Limitations

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| **Heads-up only** | Strategy is solved for 2 players. With 3+ players at the table, decisions won't be truly GTO for multi-way pots. | In a multi-player game, treat it as "me vs. field" — approximate by using the heads-up strategy against the most threatening opponent. Or solve separate 2-player strategies for different positions. |
| **Bet size abstraction** | Can't represent every possible bet size. Odd-sized bets from LLMs get snapped to nearest abstract size. | Use 4-5 abstract sizes (check, 0.33x pot, 0.67x pot, 1x pot, all-in) to cover most strategic scenarios. |
| **Translation fidelity** | PokerKit and OpenSpiel represent state differently. The translation layer (Step 3) is a lossy bridge — bet snapping and off-tree handling introduce approximation error. | Thorough testing with recorded hand histories. Log every snap decision so we can measure how often the solver hits an exact vs. approximate match. |
| **Card abstraction** | Hands in the same bucket are treated identically. Loses some board-texture reads. | Use enough buckets (~200 per street) and equity-based clustering. Good enough for ~85-90% GTO accuracy. |
| **Static strategy** | Doesn't adapt to opponent tendencies. Pure GTO doesn't exploit. | This is actually the point — GTO is the unexploitable baseline. LLMs that exploit weaknesses should theoretically beat GTO against bad players but not against each other. |
| **Precomputation time** | Card bucketing + CFR solving could take hours on first run. | One-time cost. Cache everything to disk. Could offer a "lite" version with fewer buckets/iterations for faster setup. |

---

## Estimated Total Effort

| Step | Effort |
|------|--------|
| 1. Install + validate | 30 min |
| 2. Game definition | 1-2 hours |
| 3. PokerKit ↔ OpenSpiel translation layer | 1.5 days |
| 4. Card abstraction | 1-2 days |
| 5. CFR+ solver | 1 day |
| 6. State mapper | 0.5 days |
| 7. CFR-GTO player | 0.5 days |
| 8. Factory registration | 30 min |
| 9. Precompute script | 1 hour |
| 10. Solver convergence tests (Kuhn/Leduc) | 0.5 days |
| 11. PokerBench spot-check accuracy | 1 day |
| 12. Slumbot live benchmark | 1 day |
| **Total** | **~8.5-10.5 days** |

Steps 3 (translation layer) and 4 (card abstraction) are the heaviest implementation lifts. Steps 10-12 form a validation pipeline that progressively builds confidence: 10 proves the solver math is correct, 11 proves decisions match reference GTO, and 12 proves the full system holds up against a real opponent.

---

## GTO Accuracy Estimate: ~85-95%

With 200 equity buckets per street, 4-5 abstract bet sizes, and 100k+ CFR+ iterations, the resulting strategy will be near-Nash equilibrium for the abstract game. The gap to true GTO comes from:
- Abstraction loss (hands in same bucket play identically)
- Bet size discretization
- Potential off-tree situations (opponent bets a size not in our abstraction)

This is the same architecture used by academic poker AI research and would be a significantly stronger benchmark than the current heuristic player.
