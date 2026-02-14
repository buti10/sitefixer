// src/modules/wpRepair/shared/action.api.ts
import api from "./http";

export type ActionStatus = {
  ok?: boolean;
  action_id: string;
  status: "queued" | "running" | "done" | "failed" | string;
  meta?: any;
  error?: string;
  [k: string]: any;
};

export type ActionFindingsResponse = {
  ok?: boolean;
  action_id?: string;
  findings?: any[];
  items?: any[];
  error?: string;
  [k: string]: any;
};

export async function getActionStatus(actionId: string): Promise<ActionStatus> {
  const { data } = await api.get(`/wp-repair/actions/${encodeURIComponent(actionId)}`);
  return data;
}

export async function getActionFindings(actionId: string): Promise<ActionFindingsResponse> {
  const { data } = await api.get(`/wp-repair/actions/${encodeURIComponent(actionId)}/findings`);
  return data;
}

/**
 * Optional: Rollback endpoint (backend may be added later).
 * Expected: POST /wp-repair/actions/:action_id/rollback
 */
export async function rollbackAction(actionId: string): Promise<any> {
  const { data } = await api.post(`/wp-repair/actions/${encodeURIComponent(actionId)}/rollback`);
  return data;
}
