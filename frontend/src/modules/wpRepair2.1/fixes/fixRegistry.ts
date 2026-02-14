// src/modules/wpRepair/fixes/fixRegistry.ts
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
  /** Backend fix_id (für Action-Historie / Polling UI). */
  backendFixId: string;

  title: string;
  description: string;
  risk: FixRisk;

  /** true = startet Action + Polling */
  isAction: boolean;

  /** optional Preview (read-only) */
  preview?: (sessionId: string, params?: any) => Promise<any>;

  /** Apply / Start (bei isAction liefert i.d.R. {ok, action_id, ...}) */
  run: (sessionId: string, params?: any) => Promise<ActionStartResponse | any>;

  /** UI-Metadaten (keine Logik!) */
  ui?: {
    hasPreview?: boolean;
    icon?: string; // Heroicons name
    paramsHint?: string; // kurze Erklärung für Inputs
    runLabel?: string;   // Button Label für run()
    previewLabel?: string; // Button Label für preview()
  };
};

export const FIXES: FixDef[] = [
  {
    key: "maintenance_remove",
    backendFixId: "maintenance_remove",
    title: "Maintenance entfernen",
    description: "Entfernt .maintenance (wenn vorhanden). Sicher – kein Risiko.",
    risk: "low",
    isAction: true,
    run: (sid) => fixMaintenanceRemove(sid),
    ui: {
      icon: "WrenchIcon",
      runLabel: "Apply",
    },
  },
  {
    key: "permissions_apply",
    backendFixId: "permissions",
    title: "Permissions anwenden",
    description: "Setzt sichere Standard-Permissions im WordPress-Root.",
    risk: "medium",
    isAction: true,
    preview: (sid, params) => permissionsPreview(sid, params),
    run: (sid, params) => permissionsApply(sid, params),
    ui: {
      hasPreview: true,
      icon: "LockClosedIcon",
      previewLabel: "Preview",
      runLabel: "Apply",
    },
  },
  {
    key: "dropins_apply",
    backendFixId: "dropins",
    title: "Drop-ins deaktivieren",
    description: "Deaktiviert problematische Cache-Dropins (z. B. object-cache.php).",
    risk: "medium",
    isAction: true,
    preview: (sid, params) => dropinsPreview(sid, params),
    run: (sid, params) => dropinsApply(sid, params?.dropins || params),
    ui: {
      hasPreview: true,
      icon: "PuzzlePieceIcon",
      paramsHint: "Kommagetrennt oder eine Datei pro Zeile",
      previewLabel: "Preview",
      runLabel: "Apply",
    },
  },
  {
    key: "core_preview",
    backendFixId: "core_integrity",
    title: "Core Integrity (Preview)",
    description: "Vergleicht WordPress-Core mit lokalem Core-Cache (read-only).",
    risk: "low",
    isAction: false,
    run: (sid, params) =>
      corePreview(sid, Number(params?.max_files || params?.maxFiles || 500)),
    ui: {
      icon: "ShieldCheckIcon",
      paramsHint: "max_files = Anzahl zu prüfender Dateien",
      runLabel: "Preview",
    },
  },
  {
    key: "core_replace_apply",
    backendFixId: "core_replace",
    title: "Core Replace",
    description: "Ersetzt manipulierte Core-Dateien inkl. Quarantäne & Rollback.",
    risk: "high",
    isAction: true,
    preview: (sid, params) => coreReplacePreview(sid, params || {}),
    run: (sid, params) => coreReplaceApply(sid, params || {}),
    ui: {
      hasPreview: true,
      icon: "ArrowPathIcon",
      paramsHint: "Achtung: schreibt Dateien. Preview dringend empfohlen.",
      previewLabel: "Preview",
      runLabel: "Apply",
    },
  },
];

export function getFix(key: FixKey): FixDef {
  const f = FIXES.find((x) => x.key === key);
  if (!f) throw new Error(`Unknown fix key: ${key}`);
  return f;
}
