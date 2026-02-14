// src/modules/wpRepair/fixes/maintenance/maintenance.fix.ts
import type { FixDef } from "../../shared/types";
import { maintenanceRemove } from "./maintenance.api";

export const maintenanceRemoveFix: FixDef = {
  key: "maintenance_remove",
  backendFixId: "maintenance_remove",
  title: "Maintenance entfernen",
  description: "Entfernt .maintenance (wenn vorhanden). Sicher – kein Risiko.",
  risk: "low",
  isAction: true,
  run: (sid) => maintenanceRemove(sid),
  ui: { icon: "WrenchIcon", runLabel: "Apply" },
};
