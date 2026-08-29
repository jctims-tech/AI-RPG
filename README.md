# AI-RPG

Proof-of-concept spike for a persistent AI-driven solo fantasy RPG platform:
software owns all authoritative game state (dice rolls, HP, inventory,
success/failure); the AI only narrates. The AI never decides an outcome --
it narrates *from* a result the program has already resolved.

This first version proves that one loop, nothing else: one hardcoded scene
(sneaking past a guard), one uncertain moment, one d20 roll resolved by the
program, and the AI narrating before and after.

## Run it

Requires Python 3 (no extra packages -- stdlib only).

```bash
export OPENROUTER_API_KEY=your-key-here
python3 game.py
```

You'll see an opening narration, then a prompt to press Enter to roll. The
program rolls the d20 itself and prints the result, then asks the AI to
narrate the consequence of that specific result.

To try a different model, edit the `MODEL` constant at the top of `game.py`.
