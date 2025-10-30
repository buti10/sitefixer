// src/api.ts
import axios from "axios";

// ein Client – und zwei Namen dafür:
export const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || "/api",
  withCredentials: true,
});
export const api = http; // Alias, damit Imports mit "api" funktionieren

// ---------------- Types ----------------
export type Ticket = {
  id: number;
  // Kunde
  customer_name?: string;
  name?: string;
  email?: string;
  cms?: string;
  domain?: string;
  beschreibung?: string;
  prio?: string;
  status?: string;
  hoster?: string;
  // Zugänge
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

function normalizeTicket(raw: any): Ticket & {
  ticket_id: number;
  ftp_host?: string; ftp_user?: string; ftp_pass?: string;
  website_user?: string; website_pass?: string;
} {
  const a = raw.access && typeof raw.access === 'object' ? raw.access : {};

  const id = Number(raw.id ?? raw.ticket_id);

  const ftp_host = raw.ftp_host ?? a.ftp_host ?? "";
  const ftp_user = raw.ftp_user ?? a.ftp_user ?? "";
  const ftp_pass = raw.ftp_pass ?? a.ftp_pass ?? "";
  const website_user = raw.website_user ?? a.website_user ?? "";
  const website_pass = raw.website_pass ?? a.website_pass ?? "";

  return {
    // für neue Stellen
    id,
    customer_name: raw.customer_name ?? raw.name ?? "",
    name: raw.name,
    email: raw.email,
    cms: raw.cms,
    domain: raw.domain,
    beschreibung: raw.beschreibung,
    prio: raw.prio,
    status: raw.status,
    hoster: raw.hoster,
    access: {
      ftp_host,
      ftp_user,
      ftp_pass,
      ftp_port: raw.ftp_port ? Number(raw.ftp_port) : undefined,
      root_path: raw.root_path || "/",
      website_user,
      website_pass,
    },

    // <<< Backward-Compat für TicketDetail.vue >>>
    ticket_id: id,
    ftp_host,
    ftp_user,
    ftp_pass,
    website_user,
    website_pass,
  };
}

export type Scan = {
  id: number;
  ticket_id: number;
  status: "queued" | "running" | "ok" | "issues" | "failed" | "canceled";
  progress: number;
  started_at?: string | null;
  finished_at?: string | null;
  root?: string
  options?: any
  summary?: any;
  findings?: any;
  log_tail?: string | null;
  report_url?: string | null;
};

export type SftpEntry = {
  name: string;
  path: string;
  type: "dir" | "file";
  size?: number;
  mtime?: number; // Backend liefert Epoch (Zahl)
};

export type SftpSessionRequest = {
  ticket_id?: number;
  host: string;
  username: string;
  password: string;
  port?: number;
  root?: string;
};

export type TicketListItem = {
  id: number;
  customer_name?: string;
  domain?: string;
  status?: string;
  created_at?: string;
};

// --------------- Tickets ---------------
export async function getTickets(params?: {
  start?: string;
  end?: string;
  q?: string;
}) {
  const { data } = await api.get<TicketListItem[]>("/wp/tickets", { params });
  return data;
}

export async function getTicket(id: number) {
  const { data } = await api.get(`/wp/tickets/${id}`);
  return normalizeTicket(data);
}

// --------------- SFTP ------------------
export async function sftpCreateSession(payload:{
  ticket_id:number; host:string; username:string; password:string; port?:number; root?:string
}) {
  const { data } = await axios.post("/api/sftp/session", payload, {
    headers:{ "Content-Type":"application/json" }
  })
  // Backend liefert { sid: "..." } → hier nur den String zurückgeben
  return data.sid as string
}

export async function sftpList(sid: string, path: string) {
  const { data } = await axios.get(`/api/sftp/tree`, { params: { sid, path } })
  const items = Array.isArray(data) ? data : (data?.children ?? [])
  return items as { name: string; type: 'dir'|'file'; path?: string }[]
}

export async function sftpClose(sid: string) {
  await axios.post(`/api/sftp/close`, { sid })
}

// --------- Malware Scan / Reports -------

// src/api.ts
export function startMalwareScan(body: any) {
  return axios.post('/api/malware/start', body).then(r => r.data)
}

export async function getScan(id:number){
  const { data } = await axios.get(`/api/malware/scan/${id}`)
  return data
}


export async function getFindings(scanId: string|number) {
  const r = await fetch(`/api/malware/findings/${scanId}`)
  if (!r.ok) throw new Error('Fehler beim Laden der Findings')
  return await r.json()
}

// api.ts


export async function getMalwareFindings(scanId: string) {
  const { data } = await axios.get(`/api/malware/findings/${scanId}`);
  return data; // Array von Findings
}





export async function getLogs(id: string) {
  const { data } = await api.get(`/scan/${id}/logs`);
  return data as Array<{ ts: string; msg: string }>;
}

/*export async function getReports(id: string) {
  const { data } = await api.get(`/scan/${id}/reports`);
  return data as Array<{ id: string; title: string; type: string; url?: string | null }>;
}*/

export async function getMalwareHistory(ticketId: number) {
  return (await http.get(`/malware/history/${ticketId}`)).data
}
export async function deleteScan(id: string) {
  return (await http.delete(`/malware/scan/${id}`)).data
}
// src/api.ts (Reports)

export type ReportRow = {
  id: string
  scan_id: string
  title: string
  created_at: string
  url_pdf?: string | null
  url_html?: string | null
}

export async function getReports(scanId: string): Promise<ReportRow[]> {
  const r = await fetch(`/api/malware/reports/${encodeURIComponent(scanId)}`)
  if (!r.ok) throw new Error(await r.text())
  return await r.json()
}

export async function cancelMalwareScan(scanId: string) {
  const { data } = await api.post(`/malware/cancel/${scanId}`);
  return data;
}
// Reports – Liste pro Ticket + PDF
export const getReportsByTicket = (ticketId: number) =>
  axios.get(`/api/malware/reports/by-ticket/${ticketId}`).then(r => r.data);

export const downloadReportPdf = (reportId: string) =>
  window.open(`/api/malware/reports/${encodeURIComponent(reportId)}/pdf`, '_blank');



export async function createReport(payload: {
  scan_id: string
  title?: string
  notes?: string
  include_snippets?: boolean
  data?: any            // <- NEU: z.B. { scan, findings }
}): Promise<ReportRow> {
  const r = await fetch(`/api/malware/reports`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!r.ok) throw new Error(await r.text())
  return await r.json()
}


export async function deleteReport(id: string): Promise<void> {
  const r = await fetch(`/api/malware/reports/${encodeURIComponent(id)}`, { method:'DELETE' })
  if (!r.ok) throw new Error(await r.text())
}
export type RepairAction = { id: string; label: string; risk: "low"|"medium"|"high"; selected: boolean };
export type RepairPlan = { scan_id: number; ticket_id: number; sid: string; plan: RepairAction[] };

export async function getRepairPlan(scanId: number, ticketId: number, sid: string) {
  const { data } = await api.get<RepairPlan>(`/repair/${scanId}/plan`, { params: { ticket_id: ticketId, sid }});
  return data;
}

export async function executeRepairPlan(scanId: number, ticketId: number, sid: string, actions: string[]) {
  const { data } = await api.post(`/repair/${scanId}/execute`, { ticket_id: ticketId, sid, actions });
  return data;
}

export async function listRepairActions(scanId: number) {
  const { data } = await api.get(`/repair/${scanId}/actions`);
  return data.items as Array<{id:number; action:string; status:string; started_at:string|null; finished_at:string|null}>;
}

// Comms
export const getCommsInbox = () => api.get('/comms/inbox').then(r=>r.data)
export const getMailThread = (id:number) => api.get(`/comms/mail/threads/${id}`).then(r=>r.data)
export const replyMail     = (id:number, payload:FormData) => api.post(`/comms/mail/threads/${id}/reply`, payload)
export const getChatThread = (id:number) => api.get(`/comms/chat/threads/${id}`).then(r=>r.data)
export const sendChatMsg   = (id:number, payload:{text:string}) => api.post(`/comms/chat/threads/${id}/message`, payload)


export default api;
