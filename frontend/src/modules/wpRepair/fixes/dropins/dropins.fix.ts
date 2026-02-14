// src/modules/wpRepair/fixes/dropins/dropins.fix.ts
import type { FixDef } from "../../shared/types";
import { dropinsPreview, dropinsApply } from "./dropins.api";

export const dropinsFix: FixDef = {
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
};
