# Poker RL

A project using LLMs (GPT-4o, Gemini) to play Poker via the PokerKit engine.

## Setup

1. Install the required dependencies:

```bash
pip install -r requirements.txt
```

2. Create a `.env` file with your API keys:

```bash
cp .env.example .env
```

3. Edit the `.env` file and add your API keys:

```
OPENAI_KEY=your_openai_key_here
GEMINI_KEY=your_gemini_key_here
```

## Running the Game

```bash
python test.py
```

You can set the number of hands to play via the `NUM_HANDS` environment variable:

```bash
NUM_HANDS=5 python test.py
```
