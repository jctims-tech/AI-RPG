"""Single-file Flask web version of the technical spike (game.py).

Same core logic as game.py: the AI (via OpenRouter) only ever narrates. It
never rolls a die or decides whether an action succeeds -- when the scene
reaches an uncertain moment, the AI must ask for a check via a tool call
instead of guessing, this program rolls the die itself in Python, and only
then does the AI narrate the authoritative result it's handed.

One file, one dependency (Flask), no build step, no Node/npm.

Run with:
    pip install flask
    OPENROUTER_API_KEY=... python game_web.py

Then open http://127.0.0.1:5000 in your browser.
"""

import json
import os
import random
import threading
import urllib.error
import urllib.request

from flask import Flask, jsonify, render_template_string, request

# Change this one constant to try a different model.
MODEL = "anthropic/claude-sonnet-4.6"

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

SCENE_SETUP = (
    "The player character, a lone rogue, is sneaking through a moonlit "
    "castle courtyard at night, trying to slip past Voss, a guard patrolling "
    "near the postern gate. Voss hasn't noticed anything yet."
)

# The one check this scene supports. The DC lives here, in software -- the
# model can only name which check applies, never its difficulty or result.
CHECKS = {"stealth": {"dc": 11, "label": "Sneak Past Voss"}}

SYSTEM_PROMPT_ACTION = """You are the Game Master narrating a solo tabletop-style fantasy RPG.

FIXED SCENE: %s

RULES YOU MUST FOLLOW, NO EXCEPTIONS:
- You are the narrator only. You NEVER decide whether an action succeeds or fails, and you never invent a die result.
- The player's next committed action is their attempt to get past Voss. As soon as their message describes actually moving or acting (not just looking around or asking a question), call the request_check tool with skill="stealth" instead of writing any narration about what happens next.
- If you call request_check, output ONLY the tool call. Do not also write narration text guessing the outcome.
- If the player's message is a question, hesitation, or something that doesn't yet commit to acting, respond with a short in-fiction nudge (1-3 sentences) and wait -- do not call the tool yet.
- Keep narration to 2-4 sentences, second person, present tense, moody fantasy tone.""" % SCENE_SETUP

SYSTEM_PROMPT_POST_CHECK = """You are the Game Master narrating a solo tabletop-style fantasy RPG, continuing after the scene's one uncertain moment has already been resolved.

FIXED SCENE: %s

RULES: You are the narrator only. This scene has no further checks -- just continue narrating the player's actions in 2-4 sentences, second person, present tense, consistent with everything that has already happened. Do not introduce a new encounter.""" % SCENE_SETUP

REQUEST_CHECK_TOOL = {
    "type": "function",
    "function": {
        "name": "request_check",
        "description": (
            "Call this when the player's action reaches a moment of genuine "
            "uncertainty that the game rules must resolve. Do not narrate or "
            "guess the outcome yourself -- the software will roll and tell "
            "you the result."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "skill": {
                    "type": "string",
                    "description": "Which check applies. Only 'stealth' exists in this scene.",
                    "enum": ["stealth"],
                }
            },
            "required": ["skill"],
        },
    },
}


def narrate_consequence_prompt(check, success):
    outcome = (
        "SUCCESS: the rogue slips past Voss undetected."
        if success
        else "FAILURE: Voss spots the rogue."
    )
    return (
        f'Authoritative result from the game system for the "{check["label"]}" check: {outcome}\n\n'
        "Narrate what happens in 3-5 sentences, consistent exactly with that "
        "result. Do not change, question, or re-decide it."
    )


# ---------------------------------------------------------------------------
# In-memory game state -- one campaign, one browser, no persistence needed
# for this scope. A lock guards against overlapping requests (e.g. a
# double-click while an OpenRouter call is in flight).
# ---------------------------------------------------------------------------

state_lock = threading.Lock()
_next_id = [0]


def next_id():
    _next_id[0] += 1
    return f"e{_next_id[0]}"


def fresh_player_state():
    """Placeholder shape for authoritative character state. Only inventory
    (arrows) is actually touched by this scene -- hp, resources, and
    conditions exist so the structure is there to grow into, per the ticket."""
    return {
        "hp": 12,
        "max_hp": 12,
        "inventory": {"arrows": 5, "dagger": 1},
        "resources": {"notable_ability_uses": 3, "notable_ability_max": 3},
        "conditions": [],
    }


def print_player_state():
    print("\n=== player_state ===")
    print(json.dumps(game_state["player_state"], indent=2))
    print("=====================\n")


def fresh_state():
    return {
        "player_state": fresh_player_state(),
        "check_used": False,
        "pending_check": None,
        "history": [
            {
                "id": next_id(),
                "type": "gm",
                "text": (
                    "Moonlight silvers the courtyard stones. Ahead, Voss "
                    "paces a slow line past the postern gate, spear resting "
                    "easy on his shoulder, humming something tuneless to "
                    "stay awake. You're crouched in the shadow of the well, "
                    "close enough to hear his boots on gravel. Past him, the "
                    "gate stands unlocked and unwatched -- for the next few "
                    "seconds, anyway."
                ),
            }
        ],
    }


game_state = fresh_state()


# ---------------------------------------------------------------------------
# OpenRouter client (stdlib only, same pattern as game.py)
# ---------------------------------------------------------------------------


def call_openrouter(system_prompt, messages, tools=None):
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY environment variable is not set.")

    body = {"model": MODEL, "messages": [{"role": "system", "content": system_prompt}] + messages}
    if tools:
        body["tools"] = tools

    req = urllib.request.Request(
        OPENROUTER_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"OpenRouter request failed ({e.code}): {e.read().decode('utf-8')}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Could not reach OpenRouter: {e.reason}")

    message = data["choices"][0]["message"]
    tool_calls = message.get("tool_calls")
    if tool_calls:
        call = tool_calls[0]
        return {"type": "tool_call", "name": call["function"]["name"], "arguments": json.loads(call["function"]["arguments"] or "{}")}
    return {"type": "text", "text": (message.get("content") or "").strip()}


def history_to_messages(history):
    messages = []
    for entry in history:
        if entry["type"] == "player":
            messages.append({"role": "user", "content": entry["text"]})
        elif entry["type"] == "gm":
            messages.append({"role": "assistant", "content": entry["text"]})
        elif entry["type"] == "roll" and entry["resolved"]:
            outcome = "SUCCESS" if entry["pass"] else "FAILURE"
            messages.append(
                {
                    "role": "system",
                    "content": f"[Resolved check: {entry['roll']['label']} — {entry['val']} vs DC {entry['roll']['dc']} — {outcome}]",
                }
            )
    return messages


# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

app = Flask(__name__)


@app.get("/")
def index():
    return render_template_string(PAGE_HTML)


@app.get("/api/state")
def get_state():
    with state_lock:
        return jsonify(game_state)


@app.post("/api/action")
def post_action():
    message = (request.get_json(silent=True) or {}).get("message", "").strip()
    if not message:
        return jsonify({"error": "message is required"}), 400

    with state_lock:
        if game_state["pending_check"]:
            return jsonify({"error": "A check is already pending resolution."}), 409

        game_state["history"].append({"id": next_id(), "type": "player", "text": message})

        try:
            messages = history_to_messages(game_state["history"])
            if game_state["check_used"]:
                result = call_openrouter(SYSTEM_PROMPT_POST_CHECK, messages)
            else:
                result = call_openrouter(SYSTEM_PROMPT_ACTION, messages, tools=[REQUEST_CHECK_TOOL])
        except RuntimeError as err:
            # Nothing is saved on failure -- the player's message above lives
            # only in this in-memory copy, which we discard by not proceeding.
            game_state["history"].pop()
            return jsonify({"error": str(err)}), 502

        if result["type"] == "tool_call" and result["name"] == "request_check":
            skill = result["arguments"].get("skill")
            check = CHECKS.get(skill)
            if not check:
                return jsonify({"error": f'GM requested unknown check skill "{skill}"'}), 502

            entry_id = next_id()
            game_state["history"].append(
                {
                    "id": entry_id,
                    "type": "roll",
                    "roll": {"skill": skill, "label": check["label"], "dc": check["dc"]},
                    "resolved": False,
                    "val": None,
                    "pass": None,
                }
            )
            game_state["pending_check"] = {"entry_id": entry_id, "skill": skill, "label": check["label"], "dc": check["dc"]}
        else:
            game_state["history"].append({"id": next_id(), "type": "gm", "text": result["text"]})

        print_player_state()
        return jsonify(game_state)


@app.post("/api/roll")
def post_roll():
    with state_lock:
        pending = game_state["pending_check"]
        if not pending:
            return jsonify({"error": "No check is pending."}), 409

        # Software rolls the die. The AI never sees this until it's final.
        val = random.randint(1, 20)
        success = val >= pending["dc"]

        for entry in game_state["history"]:
            if entry["id"] == pending["entry_id"]:
                entry["resolved"] = True
                entry["val"] = val
                entry["pass"] = success
                break

        game_state["check_used"] = True
        game_state["pending_check"] = None

        try:
            messages = history_to_messages(game_state["history"])
            prompt = narrate_consequence_prompt(pending, success)
            result = call_openrouter(SYSTEM_PROMPT_POST_CHECK, messages + [{"role": "user", "content": prompt}])
            text = result["text"] if result["type"] == "text" else ""
        except RuntimeError as err:
            # The roll itself already happened and is already recorded above --
            # only the narration call failed, so report that distinctly but
            # still return the (already-updated) authoritative state.
            print_player_state()
            return jsonify({"error": str(err), "state": game_state}), 502

        game_state["history"].append({"id": next_id(), "type": "gm", "text": text})
        print_player_state()
        return jsonify(game_state)


PAGE_HTML = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI-RPG</title>
<style>
  :root {
    --ink: #15181f;
    --panel: #1f2531;
    --text: #f5f1e7;
    --muted: #b9c0cc;
    --ember: #e27b45;
    --ember-dim: #7a4126;
    --sage: #8cc2a8;
    --sage-dim: #3f5e4f;
    --border: rgba(255,255,255,0.10);
    --border-soft: rgba(255,255,255,0.06);
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; margin: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, sans-serif;
    background: #000;
    display: flex;
    justify-content: center;
  }
  .shell {
    width: 100%;
    max-width: 560px;
    height: 100vh;
    background: var(--ink);
    color: var(--text);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .topbar {
    padding: 14px 16px 10px;
    border-bottom: 1px solid var(--border-soft);
    flex-shrink: 0;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .topbar h1 { font-size: 15px; margin: 0; font-weight: 600; }
  .arrows { font-size: 12px; color: var(--muted); font-variant-numeric: tabular-nums; }
  .feed {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .gm-line { font-size: 16px; line-height: 1.6; margin: 0; }
  .player-row { display: flex; justify-content: flex-end; }
  .player-bubble {
    max-width: 85%;
    background: rgba(226,123,69,0.14);
    border: 1px solid rgba(226,123,69,0.32);
    border-radius: 16px 16px 4px 16px;
    padding: 8px 13px;
  }
  .player-tag { font-size: 10px; color: var(--ember); margin: 0 0 2px; letter-spacing: 0.06em; }
  .player-text { font-size: 14.5px; margin: 0; }
  .rollcard {
    border: 1px solid var(--border);
    background: var(--panel);
    border-radius: 14px;
    padding: 14px;
  }
  .rollcard-top {
    display: flex;
    justify-content: space-between;
    font-size: 11px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 6px;
  }
  .rollcard-title { font-size: 16px; font-weight: 600; margin: 0 0 12px; }
  .rollbtn {
    display: block;
    margin: 0 auto;
    background: var(--ember);
    color: #fff;
    border: none;
    border-radius: 999px;
    padding: 10px 28px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
  }
  .rollbtn:disabled { opacity: 0.5; cursor: default; }
  .rollresult {
    text-align: center;
    font-size: 14px;
    margin: 0;
  }
  .rollresult .val { font-size: 22px; font-weight: 700; display: block; margin-bottom: 4px; }
  .pass { color: var(--sage); }
  .fail { color: var(--ember); }
  .errorbar {
    margin: 0;
    padding: 8px 16px;
    background: rgba(226,123,69,0.16);
    color: var(--ember);
    font-size: 12.5px;
    flex-shrink: 0;
  }
  .inputbar {
    flex-shrink: 0;
    border-top: 1px solid var(--border-soft);
    padding: 10px;
    display: flex;
    gap: 8px;
  }
  .textinput {
    flex: 1;
    resize: none;
    background: rgba(255,255,255,0.05);
    border: 1px solid var(--border);
    border-radius: 18px;
    padding: 10px 14px;
    font-size: 15px;
    color: var(--text);
    font-family: inherit;
  }
  .textinput:focus { outline: none; border-color: rgba(226,123,69,0.55); }
  .textinput:disabled { opacity: 0.45; }
  .sendbtn {
    flex-shrink: 0;
    border-radius: 18px;
    padding: 0 18px;
    background: var(--ember);
    border: none;
    color: #fff;
    font-weight: 600;
    cursor: pointer;
  }
  .sendbtn:disabled { opacity: 0.3; cursor: default; }
  .thinking { text-align: center; font-size: 12px; font-style: italic; color: var(--muted); }
</style>
</head>
<body>
  <div class="shell">
    <div class="topbar">
      <h1>The Postern Gate — Night</h1>
      <span class="arrows" id="arrows">Arrows: 5</span>
    </div>
    <div class="feed" id="feed"></div>
    <div class="errorbar" id="errorbar" style="display:none"></div>
    <div class="inputbar">
      <textarea id="input" class="textinput" rows="1" placeholder="What does your character do?"></textarea>
      <button id="send" class="sendbtn">Send</button>
    </div>
  </div>

<script>
let state = null;
let busy = false;

const feedEl = document.getElementById('feed');
const arrowsEl = document.getElementById('arrows');
const errorEl = document.getElementById('errorbar');
const inputEl = document.getElementById('input');
const sendEl = document.getElementById('send');

async function api(path, opts) {
  const res = await fetch(path, {
    method: (opts && opts.method) || 'GET',
    headers: opts && opts.body ? {'Content-Type': 'application/json'} : undefined,
    body: opts && opts.body ? JSON.stringify(opts.body) : undefined,
  });
  const data = await res.json();
  if (!res.ok) {
    const err = new Error(data.error || ('Request failed (' + res.status + ')'));
    err.data = data;
    throw err;
  }
  return data;
}

function setBusy(b) {
  busy = b;
  inputEl.disabled = b || (state && state.pending_check);
  sendEl.disabled = b || (state && state.pending_check) || !inputEl.value.trim();
}

function showError(msg) {
  errorEl.textContent = msg;
  errorEl.style.display = msg ? 'block' : 'none';
}

function render() {
  feedEl.innerHTML = '';
  arrowsEl.textContent = 'Arrows: ' + state.player_state.inventory.arrows;

  for (const entry of state.history) {
    if (entry.type === 'gm') {
      const p = document.createElement('p');
      p.className = 'gm-line';
      p.textContent = entry.text;
      feedEl.appendChild(p);
    } else if (entry.type === 'player') {
      const row = document.createElement('div');
      row.className = 'player-row';
      row.innerHTML = '<div class="player-bubble"><p class="player-tag">YOU</p><p class="player-text"></p></div>';
      row.querySelector('.player-text').textContent = entry.text;
      feedEl.appendChild(row);
    } else if (entry.type === 'roll') {
      const card = document.createElement('div');
      card.className = 'rollcard';
      if (!entry.resolved) {
        card.innerHTML =
          '<div class="rollcard-top"><span>Uncertain Outcome</span><span>Beat ' + entry.roll.dc + '</span></div>' +
          '<p class="rollcard-title">' + entry.roll.label + '</p>' +
          '<button class="rollbtn">Roll</button>';
        const btn = card.querySelector('.rollbtn');
        btn.addEventListener('click', doRoll);
        if (busy) btn.disabled = true;
      } else {
        const passed = entry.pass;
        card.innerHTML =
          '<div class="rollcard-top"><span>Resolved</span><span>Beat ' + entry.roll.dc + '</span></div>' +
          '<p class="rollcard-title">' + entry.roll.label + '</p>' +
          '<p class="rollresult"><span class="val ' + (passed ? 'pass' : 'fail') + '">' + entry.val + '</span>' +
          (passed ? '<span class="pass">Success</span>' : '<span class="fail">Failure</span>') + '</p>';
      }
      feedEl.appendChild(card);
    }
  }

  if (busy && !(state.pending_check)) {
    const p = document.createElement('p');
    p.className = 'thinking';
    p.textContent = 'The GM is thinking…';
    feedEl.appendChild(p);
  }

  feedEl.scrollTop = feedEl.scrollHeight;
  setBusy(busy);
}

async function loadState() {
  try {
    state = await api('/api/state');
    render();
  } catch (e) {
    showError(e.message);
  }
}

async function sendAction() {
  const text = inputEl.value.trim();
  if (!text || busy || (state && state.pending_check)) return;
  inputEl.value = '';
  showError('');
  setBusy(true);
  render();
  try {
    state = await api('/api/action', {method: 'POST', body: {message: text}});
  } catch (e) {
    showError(e.message);
  } finally {
    setBusy(false);
    render();
  }
}

async function doRoll() {
  showError('');
  setBusy(true);
  render();
  try {
    state = await api('/api/roll', {method: 'POST'});
  } catch (e) {
    showError(e.message);
    if (e.data && e.data.state) state = e.data.state;
  } finally {
    setBusy(false);
    render();
  }
}

sendEl.addEventListener('click', sendAction);
inputEl.addEventListener('input', () => setBusy(busy));
inputEl.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendAction();
  }
});

loadState();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    app.run(debug=False, port=5000)
