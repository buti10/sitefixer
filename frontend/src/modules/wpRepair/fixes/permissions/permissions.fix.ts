// src/modules/wpRepair/fixes/permissions/permissions.fix.ts
import type { FixDef } from "../../shared/types";
import { permissionsPreview, permissionsApply } from "./permissions.api";

export const permissionsFix: FixDef = {
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
};
