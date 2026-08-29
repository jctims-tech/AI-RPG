// Preconfigured test scenario for the persistent-gameplay vertical slice.
// Fictional setting adapted from the mobile UX reference prototype; the
// mechanics below are new and are NOT taken from that prototype's
// hardcoded/fake roll logic.

export const OPENING_NARRATION =
  "The Salt Road Checkpoint hunches in the dark ahead — a knot of " +
  "lantern-light and low fences at the border of the Ashwood tithe-lands. " +
  "Sable crouches beside you in the ditch grass, her knife already loosened " +
  "in its sheath. “Watch the near tower,” she breathes. “Guard walks the " +
  "fence every forty paces. When he turns, we go.” Past the checkpoint, the " +
  "supply yard sits dark and unwatched. For now.";

export const INITIAL_STATE = {
  location: "The Salt Road Checkpoint — Night",
  hp: 12,
  maxHp: 12,
  arrows: 8,
  conditions: [],
  checkUsed: false,
  pendingCheck: null,
  history: [{ id: "e0", type: "gm", text: OPENING_NARRATION }],
};

// The one check this scenario supports. DC lives in software, not the LLM --
// the model can only name which check applies, never its difficulty or result.
export const CHECKS = {
  stealth: { dc: 11, label: "Sneak Past the Patrol" },
};

export const SYSTEM_PROMPT_ACTION = `You are the Game Master narrating a solo tabletop-style fantasy RPG for the player character Ren.

FIXED SCENE: Ren and their companion Sable, a smuggler-turned-scout, are crouched in the ditch grass outside the Salt Road Checkpoint at night, about to attempt slipping past a patrolling guard into the supply yard beyond.

RULES YOU MUST FOLLOW, NO EXCEPTIONS:
- You are the narrator only. You NEVER decide whether an action succeeds or fails, and you never invent a die result.
- The player's next committed action is their attempt to get past the guard. As soon as their message describes actually moving or acting (not just looking around or asking a question), call the request_check tool with skill="stealth" instead of writing any narration about what happens next.
- If you call request_check, output ONLY the tool call. Do not also write narration text guessing the outcome.
- If the player's message is a question, hesitation, or something that doesn't yet commit to acting, respond with a short in-fiction nudge (1-3 sentences) and wait -- do not call the tool yet.
- Keep narration to 2-4 sentences, second person, present tense, moody fantasy tone.`;

export const SYSTEM_PROMPT_ACTION_POST_CHECK = `You are the Game Master narrating a solo tabletop-style fantasy RPG for the player character Ren, continuing after the scene's one uncertain moment has already been resolved.

FIXED SCENE: Ren and Sable are now in the supply yard beyond the checkpoint, past the guard.

RULES: You are the narrator only. This scene has no further checks -- just continue narrating the player's actions in 2-4 sentences, second person, present tense, consistent with everything that has already happened. Do not introduce a new combat encounter or any other check.`;

export const REQUEST_CHECK_TOOL = {
  type: "function",
  function: {
    name: "request_check",
    description:
      "Call this when the player's action reaches a moment of genuine uncertainty that the game rules must resolve. Do not narrate or guess the outcome yourself -- the software will roll and tell you the result.",
    parameters: {
      type: "object",
      properties: {
        skill: {
          type: "string",
          description: "Which check applies. Only 'stealth' exists in this scene.",
          enum: ["stealth"],
        },
      },
      required: ["skill"],
    },
  },
};

export function narrateConsequencePrompt(check, pass) {
  const outcome = pass
    ? "SUCCESS: Ren slips past the guard cleanly and reaches the supply yard undetected."
    : "FAILURE: gravel shifts underfoot and the guard's head snaps toward the sound, but Sable yanks Ren into shadow just in time -- they are not caught, but it was close, and Ren is left Shaken as they reach the supply yard.";

  return `Authoritative result from the game system for the "${check.label}" check: ${outcome}

Narrate what happens in 3-5 sentences, consistent exactly with that result. Do not change, question, or re-decide it. End with Ren and Sable arriving in the supply yard. Do not introduce a new encounter.`;
}
