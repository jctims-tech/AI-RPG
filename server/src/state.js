import { randomUUID } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { INITIAL_STATE } from "./scenario.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const DATA_FILE = join(__dirname, "..", "data", "campaign.json");

export function loadState() {
  if (!existsSync(DATA_FILE)) {
    saveState(INITIAL_STATE);
    return structuredClone(INITIAL_STATE);
  }
  return JSON.parse(readFileSync(DATA_FILE, "utf-8"));
}

export function saveState(state) {
  mkdirSync(dirname(DATA_FILE), { recursive: true });
  writeFileSync(DATA_FILE, JSON.stringify(state, null, 2));
}

export function nextEntryId() {
  return randomUUID();
}
