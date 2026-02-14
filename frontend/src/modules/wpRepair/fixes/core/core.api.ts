// src/modules/wpRepair/fixes/core/core.api.ts
import api from "../../shared/http";
import type { ActionStartResponse } from "../../shared/types";

export async function coreIntegrityPreview(sessionId: string, maxFiles = 500): Promise<any> {
  const { data } = await api.post("/wp-repair/core/preview", {
    session_id: sessionId,
    max_files: maxFiles,
  });
  return data;
}

export async function coreReplacePreview(sessionId: string, opts?: Record<string, any>): Promise<any> {
  const { data } = await api.post("/wp-repair/core/replace/preview", {
    session_id: sessionId,
    ...(opts || {}),
  });
  return data;
}

export async function coreReplaceApply(sessionId: string, opts?: Record<string, any>): Promise<ActionStartResponse> {
  const { data } = await api.post("/wp-repair/core/replace/apply", {
    session_id: sessionId,
    ...(opts || {}),
  });
  return data;
}
