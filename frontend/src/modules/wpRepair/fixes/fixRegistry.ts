// src/modules/wpRepair/fixes/fixRegistry.ts
// Backward-compatible re-export (older imports remain valid)
export type { FixDef, FixKey, FixRisk, ActionStartResponse } from "../shared/types";
export { FIXES, getFix } from "./registry";
