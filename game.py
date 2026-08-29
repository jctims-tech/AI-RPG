"""Proof-of-concept spike: AI narrates, the program resolves uncertainty.

The AI (via OpenRouter) only ever narrates. It never decides whether an
action succeeds or fails -- when the scene reaches an uncertain moment, this
program stops, rolls the die itself, and hands the AI back an authoritative
result to narrate from.

Run with: OPENROUTER_API_KEY=... python game.py
"""

import json
import os
import random
import sys
import urllib.error
import urllib.request

# Change this one constant to try a different model.
MODEL = "anthropic/claude-sonnet-4-6"

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

SCENE_SETUP = (
    "The player character, a lone rogue, is sneaking through a moonlit "
    "castle courtyard at night, trying to slip past a guard patrolling near "
    "the postern gate. The guard hasn't noticed anything yet."
)

SNEAK_DC = 11


def call_openrouter(messages):
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    payload = json.dumps({"model": MODEL, "messages": messages}).encode("utf-8")
    request = urllib.request.Request(
        OPENROUTER_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"ERROR: OpenRouter request failed ({e.code}): {e.read().decode('utf-8')}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"ERROR: could not reach OpenRouter: {e.reason}", file=sys.stderr)
        sys.exit(1)

    return body["choices"][0]["message"]["content"].strip()


def narrate_opening():
    messages = [
        {
            "role": "system",
            "content": (
                "You are the narrator for a solo tabletop-style fantasy RPG. "
                "You ONLY narrate -- you never decide whether an action "
                "succeeds or fails. When the scene reaches a moment of real "
                "uncertainty, stop narrating right before the outcome and "
                "let the game system handle it."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Scene: {SCENE_SETUP}\n\n"
                "Write a short (3-5 sentence) opening narration for this "
                "scene. End right as the character commits to sneaking past "
                "the guard, at the moment where success or failure is still "
                "unknown. Do not say whether they succeed or get caught."
            ),
        },
    ]
    return call_openrouter(messages)


def narrate_outcome(success):
    result_text = (
        "SUCCESS: the character slips past the guard undetected."
        if success
        else "FAILURE: the guard spots the character."
    )
    messages = [
        {
            "role": "system",
            "content": (
                "You are the narrator for a solo tabletop-style fantasy RPG. "
                "The game system has already determined the outcome of the "
                "player's action. Your only job is to narrate the "
                "consequences of that outcome vividly. You must NOT change, "
                "question, or re-decide the outcome -- treat it as an "
                "established fact."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Scene: {SCENE_SETUP}\n\n"
                f"Authoritative result from the game system: {result_text}\n\n"
                "Narrate what happens next in 3-5 sentences, consistent with "
                "that exact result."
            ),
        },
    ]
    return call_openrouter(messages)


def main():
    game_state = {"arrows": 5}

    print("=" * 60)
    print(narrate_opening())
    print("=" * 60)

    input("\nRoll needed: Sneak past the patrol. Press Enter to roll.\n")

    roll = random.randint(1, 20)
    success = roll >= SNEAK_DC
    print(f"\nRoll: {roll} vs DC {SNEAK_DC} -> {'SUCCESS' if success else 'FAILURE'}\n")

    print("=" * 60)
    print(narrate_outcome(success))
    print("=" * 60)

    print(f"\n[state] arrows: {game_state['arrows']} (unchanged this scene)")


if __name__ == "__main__":
    main()
