// src/modules/wpRepair/fixes/core/core.fix.ts
import type { FixDef } from "../../shared/types";
import { coreIntegrityPreview, coreReplacePreview, coreReplaceApply } from "./core.api";

export const coreIntegrityFix: FixDef = {
  key: "core_preview",
  backendFixId: "core_integrity",
  title: "Core Integrity (Preview)",
  description: "Vergleicht WordPress-Core mit lokalem Core-Cache (read-only).",
  risk: "low",
  isAction: false,
  run: (sid, params) => coreIntegrityPreview(sid, Number(params?.max_files || params?.maxFiles || 500)),
  ui: {
    icon: "ShieldCheckIcon",
    paramsHint: "max_files = Anzahl zu prüfender Dateien",
    runLabel: "Preview",
  },
};

export const coreReplaceFix: FixDef = {
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
};
