// src/modules/wpRepair/api/wpRepair.ts
// NOTE: This file is the single source of truth for the WP-Repair backend routes.
// All paths here are relative to the axios baseURL (default: /api).

import api from "@/api";

// =========================
// Types
// =========================

export type OkResp = { ok: boolean; error?: string };

export type ActionStartResponse = {
  ok: boolean;
  action_id?: string;
  error?: string;
};

export type WpRepairSession = {
  ok: boolean;
  session_id?: string;
  error?: string;
};

export type WpRepairConnectionTest = {
  ok: boolean;
  message?: string;
  error?: string;
};

export type SftpProjectItem = {
  label: string;
  root_path: string;
};

export type SftpProjectsResponse = {
  ok: boolean;
  items?: SftpProjectItem[];
  error?: string;
};

export type ActionStatus = {
  ok?: boolean;
  action_id: string;
  status: "queued" | "running" | "done" | "failed";
  meta?: any;
  error?: string;
};

export type ActionFindingsResponse = {
  ok?: boolean;
  action_id?: string;
  findings?: any[];
  error?: string;
};

// =========================
// Health
// =========================

export async function health() {
  const { data } = await api.get("/wp-repair/health");
  return data as { ok: boolean; service?: string; version?: string; error?: string };
}

// =========================
// Session / SFTP
// =========================

/**
 * Starts a WP-Repair session.
 * The backend expects the FTP credentials (from ticket) and returns a session_id.
 */
export async function startSession(ticket: any): Promise<WpRepairSession> {
  const payload = {
    ticket_id: Number(ticket?.ticket_id || ticket?.id || 0),
    ftp_host:
      ticket?.ftp_host ||
      ticket?.ftp_server ||
      ticket?.zugang_ftp_host ||
      ticket?.host ||
      ticket?.access?.ftp_host ||
      "",
    ftp_port: Number(ticket?.ftp_port || ticket?.zugang_ftp_port || ticket?.access?.ftp_port || 22),
    ftp_user:
      ticket?.ftp_user ||
      ticket?.zugang_ftp_user ||
      ticket?.username ||
      ticket?.access?.ftp_user ||
      "",
    ftp_pass:
      ticket?.ftp_pass ||
      ticket?.zugang_ftp_pass ||
      ticket?.password ||
      ticket?.access?.ftp_pass ||
      "",
  };

  const { data } = await api.post("/wp-repair/session/start", payload);
  return data;
}

/**
 * Connects SFTP for the given session.
 * (Backend-verified endpoint: POST /api/wp-repair/sftp/connect)
 */
export async function sftpConnect(sessionId: string): Promise<WpRepairConnectionTest> {
  const { data } = await api.post("/wp-repair/sftp/connect", { session_id: sessionId });
  return data;
}

export async function listProjects(sessionId: string): Promise<SftpProjectsResponse> {
  const { data } = await api.get("/wp-repair/sftp/projects", {
    params: { session_id: sessionId },
  });
  return data;
}

export async function selectProject(sessionId: string, projectRoot: string): Promise<OkResp & { project_root?: string }> {
  const { data } = await api.post("/wp-repair/sftp/select_project", {
    session_id: sessionId,
    project_root: projectRoot,
  });
  return data;
}

export async function findWpRoot(sessionId: string, maxDepth = 5): Promise<any> {
  const { data } = await api.post("/wp-repair/sftp/find_wp_root", {
    session_id: sessionId,
    max_depth: maxDepth,
  });
  return data;
}

export async function selectWpRoot(sessionId: string, wpRoot: string): Promise<OkResp & { wp_root?: string }> {
  const { data } = await api.post("/wp-repair/sftp/select_wp_root", {
    session_id: sessionId,
    wp_root: wpRoot,
  });
  return data;
}

// =========================
// Diagnose
// =========================

export async function runDiagnose(sessionId: string): Promise<any> {
  const { data } = await api.post("/wp-repair/diagnose", { session_id: sessionId });
  return data;
}

// =========================
// Actions (Polling)
// =========================

export async function getActionStatus(actionId: string): Promise<ActionStatus> {
  const { data } = await api.get(`/wp-repair/actions/${encodeURIComponent(actionId)}`);
  return data;
}

export async function getActionFindings(actionId: string): Promise<ActionFindingsResponse> {
  const { data } = await api.get(`/wp-repair/actions/${encodeURIComponent(actionId)}/findings`);
  return data;
}

// =========================
// Fixes
// =========================

export async function fixMaintenanceRemove(sessionId: string): Promise<ActionStartResponse> {
  const { data } = await api.post("/wp-repair/fix/maintenance/remove", { session_id: sessionId });
  return data;
}

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

// =========================
// Core
// =========================

export async function corePreview(sessionId: string, maxFiles = 500): Promise<any> {
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

// =========================
// Audit (optional, for HistoryStep)
// =========================

export async function auditListActions(params?: { ticket_id?: number; wp_root?: string; limit?: number }) {
  const { data } = await api.get("/wp-repair/audit/actions", { params });
  return data;
}
