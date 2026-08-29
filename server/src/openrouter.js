// Thin OpenRouter chat-completions client. The model is a single constant
// so it's easy to swap.
const MODEL = "anthropic/claude-sonnet-4-6";
const OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions";

export async function callGM({ systemPrompt, messages, tools }) {
  const apiKey = process.env.OPENROUTER_API_KEY;
  if (!apiKey) {
    throw new Error("OPENROUTER_API_KEY environment variable is not set.");
  }

  const body = {
    model: MODEL,
    messages: [{ role: "system", content: systemPrompt }, ...messages],
  };
  if (tools) body.tools = tools;

  const response = await fetch(OPENROUTER_URL, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`OpenRouter request failed (${response.status}): ${text}`);
  }

  const data = await response.json();
  const message = data.choices[0].message;

  const toolCall = message.tool_calls && message.tool_calls[0];
  if (toolCall) {
    return {
      type: "tool_call",
      name: toolCall.function.name,
      arguments: JSON.parse(toolCall.function.arguments || "{}"),
    };
  }

  return { type: "text", text: (message.content || "").trim() };
}

// Turns persisted event history into a chat-message array for the next call.
export function historyToMessages(history) {
  return history
    .filter((e) => e.type !== "roll" || e.resolved)
    .map((e) => {
      if (e.type === "player") return { role: "user", content: e.text };
      if (e.type === "gm") return { role: "assistant", content: e.text };
      if (e.type === "roll") {
        return {
          role: "system",
          content: `[Resolved check: ${e.roll.label} — ${e.val} vs DC ${e.roll.dc} — ${
            e.pass ? "SUCCESS" : "FAILURE"
          }]`,
        };
      }
      if (e.type === "note") return { role: "system", content: e.text };
      return null;
    })
    .filter(Boolean);
}
