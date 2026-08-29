import { useEffect, useRef, useState } from "react";
import "./styles.css";

async function api(path, options) {
  const res = await fetch(path, {
    method: options?.method || "GET",
    headers: options?.body ? { "Content-Type": "application/json" } : undefined,
    body: options?.body ? JSON.stringify(options.body) : undefined,
  });
  const data = await res.json();
  if (!res.ok) {
    const err = new Error(data.error || `Request failed (${res.status})`);
    err.data = data;
    throw err;
  }
  return data;
}

function RollCard({ roll, onRoll, disabled }) {
  const [rolling, setRolling] = useState(false);
  const [cycleVal, setCycleVal] = useState(1);
  const intervalRef = useRef(null);

  const handleTap = async () => {
    if (rolling || disabled) return;
    setRolling(true);
    intervalRef.current = setInterval(() => setCycleVal(1 + Math.floor(Math.random() * 20)), 80);
    try {
      await onRoll();
    } finally {
      clearInterval(intervalRef.current);
      setRolling(false);
    }
  };

  return (
    <div className="rollcard">
      <div className="rollcard-top">
        <span className="rollcard-kicker">Uncertain Outcome</span>
        <span className="rollcard-target">Beat {roll.dc}</span>
      </div>
      <p className="rollcard-title">{roll.label}</p>
      <div className="dieblock">
        <button className="die-btn" onClick={handleTap} disabled={rolling || disabled} aria-label="Roll the die">
          <span className={`die-shape die-idle ${rolling ? "die-tumble" : ""}`} />
          <span className="die-value">{rolling ? cycleVal : "?"}</span>
        </button>
        <p className="rollcaption">{rolling ? "Rolling…" : "Tap to roll"}</p>
      </div>
    </div>
  );
}

function ResolvedRoll({ entry }) {
  const { roll, val, pass } = entry;
  return (
    <div className="rollcard resolved">
      <div className="rollcard-top">
        <span className="rollcard-kicker">Resolved</span>
        <span className="rollcard-target">Beat {roll.dc}</span>
      </div>
      <p className="rollcard-title">{roll.label}</p>
      <div className="dieblock">
        <span className={`die-shape ${pass ? "die-success" : "die-fail"}`} />
        <p className="rollresult">
          {val} vs {roll.dc} — <span className={pass ? "pass" : "fail"}>{pass ? "Success" : "Failure"}</span>
        </p>
      </div>
    </div>
  );
}

export default function App() {
  const [state, setState] = useState(null);
  const [inputValue, setInputValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const feedRef = useRef(null);

  useEffect(() => {
    api("/api/state")
      .then(setState)
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (feedRef.current) feedRef.current.scrollTop = feedRef.current.scrollHeight;
  }, [state]);

  const handleSend = async () => {
    const text = inputValue.trim();
    if (!text || busy || state?.pendingCheck) return;
    setInputValue("");
    setBusy(true);
    setError(null);
    try {
      const result = await api("/api/action", { method: "POST", body: { message: text } });
      setState(result.state);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const handleRoll = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await api("/api/roll", { method: "POST" });
      setState(result.state);
    } catch (e) {
      setError(e.message);
      // The roll itself is authoritative and may have already been resolved
      // and persisted server-side even if the GM's narration call failed --
      // reflect that instead of silently dropping it.
      if (e.data?.state) setState(e.data.state);
    } finally {
      setBusy(false);
    }
  };

  if (!state) {
    return (
      <div className="rpg-outer">
        <div className="rpg-shell">
          <p style={{ padding: 20 }}>{error ? `Error: ${error}` : "Loading campaign…"}</p>
        </div>
      </div>
    );
  }

  const disabled = busy || !!state.pendingCheck;

  return (
    <div className="rpg-outer">
      <div className="rpg-shell">
        <div className="topbar">
          <div style={{ minWidth: 0 }}>
            <p className="eyebrow">Campaign</p>
            <p className="title">{state.location}</p>
          </div>
          <div className="hpbadge">
            <span className="renbadge">R</span>
            <span>
              {state.hp}/{state.maxHp}
            </span>
          </div>
        </div>

        <div className="presentbar">
          <span className="presentlabel">Arrows: {state.arrows}</span>
          {state.conditions.map((c) => (
            <span key={c} className="conditiontag">
              {c}
            </span>
          ))}
        </div>

        <div className="feed" ref={feedRef}>
          {state.history.map((entry) => {
            if (entry.type === "gm")
              return (
                <p key={entry.id} className="gm-line">
                  {entry.text}
                </p>
              );
            if (entry.type === "player")
              return (
                <div key={entry.id} className="player-row">
                  <div className="player-bubble">
                    <p className="player-tag">REN</p>
                    <p className="player-text">{entry.text}</p>
                  </div>
                </div>
              );
            if (entry.type === "note")
              return (
                <div key={entry.id} className="note-row">
                  <span className="note-pill">{entry.text}</span>
                </div>
              );
            if (entry.type === "roll") {
              if (entry.resolved) return <ResolvedRoll key={entry.id} entry={entry} />;
              return <RollCard key={entry.id} roll={entry.roll} onRoll={handleRoll} disabled={busy} />;
            }
            return null;
          })}
          {busy && !state.pendingCheck && <p className="note-pill thinking">The GM is thinking…</p>}
        </div>

        {error && <p className="errorbar">{error}</p>}

        <div className="inputbar">
          <textarea
            rows={1}
            className="textinput"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            disabled={disabled}
            placeholder={state.pendingCheck ? "Resolve the roll above to continue…" : "What does Ren do?"}
          />
          <button className="sendbtn" onClick={handleSend} disabled={disabled || !inputValue.trim()}>
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
