import express from "express";
import { callGM, historyToMessages } from "./openrouter.js";
import {
  CHECKS,
  REQUEST_CHECK_TOOL,
  SYSTEM_PROMPT_ACTION,
  SYSTEM_PROMPT_ACTION_POST_CHECK,
  narrateConsequencePrompt,
} from "./scenario.js";
import { loadState, nextEntryId, saveState } from "./state.js";

const app = express();
app.use(express.json());

const PORT = process.env.PORT || 3001;

app.get("/api/state", (req, res) => {
  res.json(loadState());
});

// Player sends a natural-language action. The GM either narrates freely or
// calls the request_check tool -- it never rolls or decides an outcome.
app.post("/api/action", async (req, res) => {
  const message = (req.body?.message || "").trim();
  if (!message) return res.status(400).json({ error: "message is required" });

  const state = loadState();
  if (state.pendingCheck) {
    return res.status(409).json({ error: "A check is already pending resolution." });
  }

  state.history.push({ id: nextEntryId(), type: "player", text: message });

  try {
    const messages = historyToMessages(state.history);
    const result = state.checkUsed
      ? await callGM({ systemPrompt: SYSTEM_PROMPT_ACTION_POST_CHECK, messages })
      : await callGM({ systemPrompt: SYSTEM_PROMPT_ACTION, messages, tools: [REQUEST_CHECK_TOOL] });

    if (result.type === "tool_call" && result.name === "request_check") {
      const skill = result.arguments.skill;
      const check = CHECKS[skill];
      if (!check) throw new Error(`GM requested unknown check skill "${skill}"`);

      const rollEntry = {
        id: nextEntryId(),
        type: "roll",
        roll: { skill, label: check.label, dc: check.dc },
        resolved: false,
        val: null,
        pass: null,
      };
      state.history.push(rollEntry);
      state.pendingCheck = { entryId: rollEntry.id, skill, label: check.label, dc: check.dc };
      saveState(state);
      return res.json({ type: "check_required", state });
    }

    // Defensive: even if the model narrated text alongside/instead of a
    // tool call, plain narration never resolves an outcome on its own --
    // it's just added to the log like any other GM turn.
    state.history.push({ id: nextEntryId(), type: "gm", text: result.text });
    saveState(state);
    res.json({ type: "narration", state });
  } catch (err) {
    console.error(err);
    res.status(502).json({ error: err.message });
  }
});

// Player explicitly initiates the roll for the pending check. Software (not
// the LLM) generates the result and updates authoritative state.
app.post("/api/roll", async (req, res) => {
  const state = loadState();
  const pending = state.pendingCheck;
  if (!pending) return res.status(409).json({ error: "No check is pending." });

  const val = 1 + Math.floor(Math.random() * 20);
  const pass = val >= pending.dc;

  state.history = state.history.map((e) =>
    e.id === pending.entryId ? { ...e, resolved: true, val, pass } : e
  );

  // Scenario-specific consequences: this is the one mechanical rule this
  // slice needs, kept separate from generic infrastructure above so it can
  // grow into a real rules module later.
  state.location = "Supply Yard — Night";
  if (!pass && !state.conditions.includes("Shaken")) {
    state.conditions.push("Shaken");
    state.history.push({ id: nextEntryId(), type: "note", text: "Condition added: Shaken" });
  }
  state.checkUsed = true;
  state.pendingCheck = null;
  saveState(state);

  try {
    const messages = historyToMessages(state.history);
    const prompt = narrateConsequencePrompt(pending, pass);
    const result = await callGM({
      systemPrompt: SYSTEM_PROMPT_ACTION_POST_CHECK,
      messages: [...messages, { role: "user", content: prompt }],
    });

    const text = result.type === "text" ? result.text : "";
    state.history.push({ id: nextEntryId(), type: "gm", text });
    saveState(state);

    res.json({ val, pass, dc: pending.dc, state });
  } catch (err) {
    console.error(err);
    // The roll and state change already happened and are already persisted --
    // only the narration call failed, so report that distinctly.
    res.status(502).json({ error: err.message, val, pass, dc: pending.dc, state });
  }
});

app.listen(PORT, () => {
  console.log(`AI-RPG server listening on http://localhost:${PORT}`);
});
