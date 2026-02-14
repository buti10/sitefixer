// src/modules/wpRepair/fixes/fixRegistry.ts
// Central registry for Quick-Fixes.
// Add new fixes here (metadata + api bindings) so the UI and store stay consistent.

import {
  fixMaintenanceRemove,
  permissionsPreview,
  permissionsApply,
  dropinsPreview,
  dropinsApply,
  corePreview,
  coreReplacePreview,
  coreReplaceApply,
  type ActionStartResponse,
} from "../api/wpRepair";

export type FixKey =
  | "maintenance_remove"
  | "permissions_apply"
  | "dropins_apply"
  | "core_preview"
  | "core_replace_apply";

export type FixRisk = "low" | "medium" | "high";

export type FixDef = {
  key: FixKey;
  title: string;
  description: string;
  risk: FixRisk;
  // If true -> returns an action_id and must be polled.
  isAction: boolean;
  // Optional preview function (read-only) used by UI
  preview?: (sessionId: string, params?: any) => Promise<any>;
  // Start/apply function
  run: (sessionId: string, params?: any) => Promise<ActionStartResponse | any>;
  // Basic UI hints
  ui?: {
    // Show a "Preview" button
    hasPreview?: boolean;
  };
};

export const FIXES: FixDef[] = [
  {
    key: "maintenance_remove",
    title: "Maintenance entfernen",
    description: "Entfernt .maintenance (wenn vorhanden) mit Quarantäne + Rollback.",
    risk: "low",
    isAction: true,
    run: (sid) => fixMaintenanceRemove(sid),
  },
  {
    key: "permissions_apply",
    title: "Permissions anwenden",
    description: "Setzt sichere Standard-Permissions (nur im WP-Root Bereich).",
    risk: "medium",
    isAction: true,
    preview: (sid, params) => permissionsPreview(sid, params),
    run: (sid, params) => permissionsApply(sid, params),
    ui: { hasPreview: true },
  },
  {
    key: "dropins_apply",
    title: "Drop-ins deaktivieren",
    description: "Deaktiviert Drop-ins via Rename + Audit (z. B. object-cache.php).",
    risk: "medium",
    isAction: true,
    preview: (sid, params) => dropinsPreview(sid, params),
    run: (sid, params) => dropinsApply(sid, params?.dropins || params),
    ui: { hasPreview: true },
  },
  {
    key: "core_preview",
    title: "Core Preview",
    description: "Vergleicht WP-Core gegen lokalen Core-Cache (read-only).",
    risk: "low",
    isAction: false,
    run: (sid, params) => corePreview(sid, Number(params?.max_files || params?.maxFiles || 500)),
  },
  {
    key: "core_replace_apply",
    title: "Core Replace",
    description: "Preview zeigt geplante Ersetzungen. Apply startet Action mit Quarantäne/Rollback.",
    risk: "high",
    isAction: true,
    preview: (sid, params) => coreReplacePreview(sid, params || {}),
    run: (sid, params) => coreReplaceApply(sid, params || {}),
    ui: { hasPreview: true },
  },
];

export function getFix(key: FixKey): FixDef {
  const f = FIXES.find((x) => x.key === key);
  if (!f) throw new Error(`Unknown fix key: ${key}`);
  return f;
}
