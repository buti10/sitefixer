// src/api.ts
import axios from "axios";

// -------- CSRF-Helfer --------
function getCookie(name: string): string | null {
  const m = document.cookie.match(
    new RegExp("(?:^|; )" + name.replace(/([$?*|{}\]\\^])/g, "\\$1") + "=([^;]*)")
  );
  return m ? decodeURIComponent(m[1]) : null;
}

// ein Client – und zwei Namen dafür:
export const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || "/api",
  withCredentials: true, // wichtig: Cookies (JWT + CSRF) mitschicken
});

// CSRF für Schreib-Methoden setzen
http.interceptors.request.use((config) => {
  const method = (config.method || "get").toLowerCase();
  if (["post", "put", "patch", "delete"].includes(method)) {
    const token =
      getCookie("csrf_access_token") ||
      getCookie("csrf_token") ||
      getCookie("XSRF-TOKEN");

    if (token) {
      config.headers = config.headers || {};
      (config.headers as any)["X-CSRF-TOKEN"] = token; // Flask-JWT-Extended
    }
  }
  return config;
});

http.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status;
    if (status === 401) {
      localStorage.removeItem("sf_user");
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export const api = http;
export default api;

// ---------------- Types ----------------
export type Ticket = {
  id: number;
  customer_name?: string;
  name?: string;
  email?: string;
  cms?: string;
  domain?: string;
  beschreibung?: string;
  prio?: string;
  status?: string;
  hoster?: string;
  access?: {
    ftp_host?: string;
    ftp_user?: string;
    ftp_pass?: string;
    ftp_port?: number;
    root_path?: string;
    website_user?: string;
    website_pass?: string;
  };
};

export type Scan = {
  id: number;
  ticket_id: number;
  status: "queued" | "running" | "ok" | "issues" | "failed" | "canceled";
  progress: number;
  started_at?: string | null;
  finished_at?: string | null;
  root?: string;
  options?: any;
  summary?: any;
  findings?: any;
  log_tail?: string | null;
  report_url?: string | null;
};

export type TicketListItem = {
  id: number;
  customer_name?: string;
  domain?: string;
  status?: string;
  created_at?: string;
};

// ---------------- Tickets ----------------
export async function getTickets(params?: { start?: string; end?: string; q?: string }) {
  const { data } = await api.get<TicketListItem[]>("/wp/tickets", { params });
  return data;
}

export async function getTicket(id: number) {
  const r = await api.get(`/wp/tickets/${id}`);
  return r.data;
}

// --------------- SFTP (legacy) ------------------
export async function sftpCreateSession(payload: {
  ticket_id: number;
  host: string;
  username: string;
  password: string;
  port?: number;
  root?: string;
}) {
  const { data } = await api.post("/sftp/session", payload, {
    headers: { "Content-Type": "application/json" },
  });
  return data.sid as string;
}

export async function sftpList(sid: string, path: string) {
  const { data } = await api.get(`/sftp/tree`, { params: { sid, path } });
  const items = Array.isArray(data) ? data : data?.children ?? [];
  return items as { name: string; type: "dir" | "file"; path?: string }[];
}

export async function sftpClose(sid: string) {
  await api.post(`/sftp/close`, { sid });
}

// --------- Malware Scan / Reports -------
export function startMalwareScan(body: any) {
  return api.post("/malware/start", body).then((r) => r.data);
}

export async function getScan(id: number) {
  const { data } = await api.get(`/malware/scan/${id}`);
  return data;
}

export async function cancelMalwareScan(scanId: string | number) {
  const { data } = await api.post(`/malware/cancel/${scanId}`);
  return data;
}

export async function getFindings(scanId: string | number) {
  const r = await fetch(`/api/malware/findings/${scanId}`);
  if (!r.ok) throw new Error("Fehler beim Laden der Findings");
  return await r.json();
}

export async function getMalwareFindings(scanId: string) {
  const { data } = await api.get(`/malware/findings/${scanId}`);
  return data;
}

export async function getMalwareHistory(ticketId: number) {
  return (await api.get(`/malware/history/${ticketId}`)).data;
}

export async function deleteScan(id: string) {
  return (await api.delete(`/malware/scan/${id}`)).data;
}

export async function deleteReportsByTicket(ticketId: number) {
  return api.delete(`/reports/ticket/${ticketId}`).then((r) => r.data);
}

export async function getTicketUploads(ticketId: number) {
  const res = await api.get(`/wp/tickets/${ticketId}/uploads`);
  return res.data;
}

export async function updateTicketStatus(ticketId: number, status: string) {
  const res = await api.post(`/wp/tickets/${ticketId}/status`, { status });
  return res.data;
}

// Reports
export type ReportRow = {
  id: string;
  scan_id: string;
  title: string;
  created_at: string;
  url_pdf?: string | null;
  url_html?: string | null;
};

export async function getReports(scanId: string): Promise<ReportRow[]> {
  const r = await fetch(`/api/malware/reports/${encodeURIComponent(scanId)}`);
  if (!r.ok) throw new Error(await r.text());
  return await r.json();
}

export const getReportsByTicket = (ticketId: number) =>
  api.get(`/malware/reports/by-ticket/${ticketId}`).then((r) => r.data);

export const downloadReportPdf = (reportId: string) =>
  window.open(`/api/malware/reports/${encodeURIComponent(reportId)}/pdf`, "_blank");

export async function createReport(payload: {
  scan_id: string;
  title?: string;
  notes?: string;
  include_snippets?: boolean;
  data?: any;
}): Promise<ReportRow> {
  const r = await fetch(`/api/malware/reports`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) throw new Error(await r.text());
  return await r.json();
}

export async function deleteReport(id: string): Promise<void> {
  const r = await fetch(`/api/malware/reports/${encodeURIComponent(id)}`, { method: "DELETE" });
  if (!r.ok) throw new Error(await r.text());
}

// ---------------- WP / CRM helpers ----------------
export async function getSupporters() {
  const r = await api.get("/wp/supporters");
  return r.data;
}

export async function getProducts() {
  const r = await api.get("/wp/products");
  return r.data;
}

export async function saveTicketPsa(ticketId: number, psaId: number) {
  const r = await api.post(`/wp/tickets/${ticketId}/psa`, { psa_id: psaId });
  return r.data;
}

export async function sendPaymentLink(ticketId: number, productId: number) {
  const r = await api.post(`/wp/tickets/${ticketId}/send_payment`, { product_id: productId });
  return r.data;
}

export async function getTicketNotes(ticketId: number) {
  const r = await api.get(`/wp/tickets/${ticketId}/notes`);
  return r.data;
}

export async function addTicketNote(ticketId: number, payload: { text: string; remind_at?: string }) {
  const r = await api.post(`/wp/tickets/${ticketId}/notes`, payload);
  return r.data;
}

// ---------------- Repair Legacy (ALT, unangetastet) ----------------
export type RepairAction = {
  id: string;
  label: string;
  risk: "low" | "medium" | "high";
  selected: boolean;
};

export type RepairPlan = {
  scan_id: number;
  ticket_id: number;
  sid: string;
  plan: RepairAction[];
};

export async function legacyGetRepairPlan(scanId: number, ticketId: number, sid: string) {
  const { data } = await api.get<RepairPlan>(`/repair/${scanId}/plan`, {
    params: { ticket_id: ticketId, sid },
  });
  return data;
}

export async function legacyExecuteRepairPlan(scanId: number, ticketId: number, sid: string, actions: string[]) {
  const { data } = await api.post(`/repair/${scanId}/execute`, { ticket_id: ticketId, sid, actions });
  return data;
}




// ==============================
// WP-Repair Beta API (isolated)
// Prefix: /api/wp-repair/*
// ==============================

export async function repairSftpConnect(ticketId: number) {
  const { data } = await api.post(`/wp-repair/tickets/${ticketId}/sftp/connect`, {});
  return data as { sftp_session_id: string; expires_in: number };
}

export async function repairSftpProjects(sessionId: string) {
  const { data } = await api.get(`/wp-repair/sftp/${sessionId}/projects`);
  return data as { items: Array<{ root_path: string; label?: string; wp_version?: string | null }> };
}

export async function repairSftpLs(sessionId: string, path: string) {
  const { data } = await api.get(`/wp-repair/sftp/${sessionId}/ls`, { params: { path } });
  return data as { items: Array<{ name: string; type: "dir" | "file"; size?: number | null }> };
}

export async function repairSetRoot(ticketId: number, root_path: string) {
  const { data } = await api.post(`/wp-repair/tickets/${ticketId}/root`, { root_path });
  return data as { ok: boolean; root_path: string };
}

export async function repairDiagnose(payload: {
  session_id: string;
  root_path: string;
  base_url: string;
  verify_ssl?: boolean;
  capture_snippet?: boolean;
  tail_lines?: number;
  redact_logs?: boolean;
}) {
  const { data } = await api.post(`/wp-repair/diagnose`, payload);
  return data;
}


// FIX: htaccess reset
export async function repairFixHtaccess(payload: {
  session_id: string;
  root_path: string;
  ticket_id?: number;
  dry_run?: boolean;
  keep_custom_above?: boolean;
}) {
  const { data } = await api.post(`/wp-repair/fix/htaccess/reset`, payload);
  return data;
}

// FIX: dropins disable
export async function repairFixDropins(payload: {
  session_id: string;
  root_path: string;
  ticket_id?: number;
  dry_run?: boolean;
  rename_suffix?: string;
  backup_before?: boolean;
}) {
  const { data } = await api.post(`/wp-repair/fix/cache/disable-dropins`, payload);
  return data;
}

// FIX: permissions normalize
export async function repairFixPermissions(payload: {
  session_id: string;
  root_path: string;
  ticket_id?: number;
  dry_run?: boolean;
  target?: string;
}) {
  const { data } = await api.post(`/wp-repair/fix/permissions/normalize`, payload);
  return data;
}

// FIX: maintenance remove
export async function repairFixMaintenance(payload: {
  session_id: string;
  root_path: string;
  ticket_id?: number;
  dry_run?: boolean;
  backup_before?: boolean;
}) {
  const { data } = await api.post(`/wp-repair/fix/maintenance/remove`, payload);
  return data;
}

// --- Repair: Audit / Verlauf ---
// --- Repair: Audit / Verlauf ---
export async function repairListActions(params: { root_path: string; ticket_id?: number }) {
  const res = await api.get("/wp-repair/actions", { params });
  return res.data;
}

export async function repairRollbackAction(payload: { action_id: string; session_id: string }) {
  const { action_id, ...body } = payload;
  const res = await api.post(`/wp-repair/actions/${encodeURIComponent(action_id)}/rollback`, body);
  return res.data;
}

