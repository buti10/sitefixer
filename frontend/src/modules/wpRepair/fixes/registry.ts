// src/modules/wpRepair/fixes/registry.ts
import type { FixDef, FixKey } from "../shared/types";

import { maintenanceRemoveFix } from "./maintenance/maintenance.fix";
import { permissionsFix } from "./permissions/permissions.fix";
import { dropinsFix } from "./dropins/dropins.fix";
import { coreIntegrityFix, coreReplaceFix } from "./core/core.fix";

export const FIXES: FixDef[] = [
  maintenanceRemoveFix,
  permissionsFix,
  dropinsFix,
  coreIntegrityFix,
  coreReplaceFix,
];

const MAP: Record<string, FixDef> = Object.fromEntries(FIXES.map((f) => [f.key, f]));

export function getFix(key: FixKey): FixDef {
  const f = MAP[key];
  if (!f) throw new Error(`Unknown fix key: ${key}`);
  return f;
}
