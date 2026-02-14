// src/modules/wpRepair/fixes/dropins/dropins.api.ts
import api from "../../shared/http";
import type { ActionStartResponse } from "../../shared/types";

export async function dropinsPreview(sessionId: string, payload?: Record<string, any>): Promise<any> {
  const { data } = await api.post("/wp-repair/fix/dropins/preview", {
    session_id: sessionId,
    ...(payload || {}),
  });
  return data;
}

export async function dropinsApply(sessionId: string, dropins?: string[] | null): Promise<ActionStartResponse> {
  const { data } = await api.post("/wp-repair/fix/dropins/apply", {
    session_id: sessionId,
    dropins: Array.isArray(dropins) ? dropins : undefined,
  });
  return data;
}
