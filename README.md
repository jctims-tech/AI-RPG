# AI-RPG

Persistent AI-driven solo fantasy RPG platform: software owns all
authoritative game state (dice rolls, HP, inventory, conditions,
success/failure); the AI only narrates. The AI never decides an outcome --
it narrates *from* a result the program has already resolved, and it must
stop and wait when a player-facing roll is required.

## `game.py` -- technical spike (Stage 0)

A single-file, terminal-only proof of concept: one hardcoded scene, one d20
roll resolved by plain Python, the AI narrating before and after. Superseded
by the vertical slice below, kept here as a reference.

```bash
export OPENROUTER_API_KEY=your-key-here
python3 game.py
```

## `server/` + `client/` -- persistent gameplay vertical slice (Stage 1, Ticket 001)

A playable slice proving the full loop survives closing and reopening the
app: natural-language player input -> AI GM narrates or requests a check ->
gameplay pauses -> player initiates the roll -> software resolves it ->
authoritative state updates -> AI GM narrates the consequence -> everything
persists to disk.

Uses a preconfigured test character (Ren) and scenario (sneaking past a
guard at the Salt Road Checkpoint with companion Sable), adapted from the
mobile UX reference prototype. No character creation, no full combat, no
general rules engine -- see the ticket for full scope notes.

### Run it

Requires Node.js 18+. Two processes, two terminals:

```bash
# Terminal 1 -- backend (owns the OpenRouter calls, dice rolls, and
# campaign.json persistence)
cd server
npm install
export OPENROUTER_API_KEY=your-key-here
npm start
```

```bash
# Terminal 2 -- frontend (Vite dev server, proxies /api to the backend)
cd client
npm install
npm run dev
```

Open the URL Vite prints (typically http://localhost:5173).

To reset the campaign to its starting state, stop the backend and delete
`server/data/campaign.json`, then restart it.

To try a different model, edit the `MODEL` constant at the top of
`server/src/openrouter.js`.
