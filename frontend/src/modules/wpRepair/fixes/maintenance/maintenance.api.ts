// src/modules/wpRepair/fixes/maintenance/maintenance.api.ts
import api from "../../shared/http";
import type { ActionStartResponse } from "../../shared/types";

export async function maintenanceRemove(sessionId: string): Promise<ActionStartResponse> {
  const { data } = await api.post("/wp-repair/fix/maintenance/remove", { session_id: sessionId });
  return data;
}
