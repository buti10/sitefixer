// src/modules/wpRepair/fixes/permissions/permissions.api.ts
import api from "../../shared/http";
import type { ActionStartResponse } from "../../shared/types";

export async function permissionsPreview(sessionId: string, payload?: Record<string, any>): Promise<any> {
  const { data } = await api.post("/wp-repair/permissions/preview", {
    session_id: sessionId,
    ...(payload || {}),
  });
  return data;
}

export async function permissionsApply(sessionId: string, payload?: Record<string, any>): Promise<ActionStartResponse> {
  const { data } = await api.post("/wp-repair/permissions/apply", {
    session_id: sessionId,
    ...(payload || {}),
  });
  return data;
}
