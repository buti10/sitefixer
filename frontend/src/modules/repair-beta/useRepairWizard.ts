// src/modules/repair-beta/useRepairWizard.ts
import { computed, onMounted, reactive, ref, type Ref, proxyRefs } from "vue";

import { useRoute } from "vue-router";

import {
  getTicket,
  repairSftpConnect,
  repairSftpProjects,
  repairSftpLs,
  repairSetRoot,
  repairDiagnose,
  repairFixHtaccess,
  repairFixDropins,
  repairFixPermissions,
  repairFixMaintenance,
  repairListActions,
  repairRollbackAction,
} from "../../api";

export type TabKey =
  | "overview"
  | "sftp"
  | "diagnose"
  | "quickfixes"
  | "plugins"
  | "themes"
  | "core"
  | "db"
  | "env"
  | "report"
  | "audit"
  | "explorer";

export function useRepairWizard() {
  const route = useRoute();
  const id = Number(route.params.id);

  // ---------------------------
  // Ticket-Daten (Anzeige/UX)
  // ---------------------------
  function qObj() {
    try {
      const s = String(route.query.s || "");
      return s ? JSON.parse(decodeURIComponent(atob(s))) : null;
    } catch {
      return null;
    }
  }
  function ssObj() {
    try {
      return JSON.parse(sessionStorage.getItem("sf_last_ticket") || "null");
    } catch {
      return null;
    }
  }

  const stateTicket = ref<any>(qObj() || (history.state as any)?.ticket || ssObj() || { ticket_id: id });
  const apiTicket = ref<any>({});
  const ticket = computed(() => ({ ...stateTicket.value, ...apiTicket.value }));

  const ticketLoading = ref(true);
  const ticketError = ref("");

  onMounted(async () => {
    try {
      const r = await getTicket(id);
      if (r && typeof r === "object") apiTicket.value = r;
      sessionStorage.setItem("sf_last_ticket", JSON.stringify({ ...stateTicket.value, ...apiTicket.value }));
    } catch (e: any) {
      ticketError.value = e?.response?.data?.msg || e?.message || "Ticket konnte nicht geladen werden";
    } finally {
      ticketLoading.value = false;
    }
  });

  // Felder für Anzeige
  const sftpHost = computed(() => ticket.value.ftp_host || ticket.value.ftp_server || ticket.value.zugang_ftp_host || "");
  const sftpUser = computed(() => ticket.value.ftp_user || ticket.value.zugang_ftp_user || "");
  const sftpPort = computed(() => String(ticket.value.ftp_port || ticket.value.sftp_port || "22"));
  const sftpPass = computed(() => ticket.value.ftp_pass || ticket.value.zugang_ftp_pass || "");

  const wpUser = computed(() => ticket.value.website_login || ticket.value.website_user || ticket.value.zugang_website_login || "");
  const wpPass = computed(() => ticket.value.website_pass || ticket.value.zugang_website_pass || "");

  const hostingUrl = computed(() => ticket.value.hosting_url || ticket.value.hoster_url || ticket.value.zugang_hosting_url || "");
  const hostingUser = computed(() => ticket.value.hosting_user || ticket.value.zugang_hosting_user || "");
  const hostingPass = computed(() => ticket.value.hosting_pass || ticket.value.zugang_hosting_pass || "");

  // ---------------------------
  // Password UI: show/copy
  // ---------------------------
  const show = reactive({ sftp: false, wp: false, host: false });
  const copied = ref<"sftp" | "wp" | "host" | "">("");

  async function copyToClipboard(text: string, which: "sftp" | "wp" | "host") {
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      copied.value = which;
      setTimeout(() => (copied.value = ""), 1200);
    } catch {
      // noop
    }
  }

  // ---------------------------
  // Helpers
  // ---------------------------
  function norm(u?: string) {
    return !u ? "#" : /^https?:\/\//i.test(u) ? u : `https://${u}`;
  }

  const baseUrl = computed(() => norm(ticket.value.domain || ""));

  // ---------------------------
  // SFTP Flow
  // ---------------------------
  const sessionId = ref("");
  const connecting = ref(false);
  const connectError = ref("");
  const connectInfo = ref("");

  const projects = ref<any[]>([]);
  const projectsLoading = ref(false);
  const projectsError = ref("");
  const selectedProject = ref<string | null>(null);
  const savingRoot = ref(false);
  const rootSaved = ref(false);

  const rootPathHint = computed(() => ticket.value?.repair_root || ticket.value?.root_path || "");

  async function connectSftp() {
    connecting.value = true;
    connectError.value = "";
    connectInfo.value = "";
    try {
      const res = await repairSftpConnect(id);

      if (res?.error) {
        connectError.value = String(res.error);
        sessionId.value = "";
        return;
      }

      sessionId.value = res?.sftp_session_id || "";
      if (!sessionId.value) {
        connectError.value = "Connect: keine Session-ID erhalten (Backend liefert kein sftp_session_id).";
        return;
      }

      connectInfo.value = "Verbindung hergestellt.";
      await refreshProjects();
    } catch (e: any) {
      connectError.value = e?.response?.data?.error || e?.response?.data?.msg || e?.message || "SFTP Connect fehlgeschlagen";
    } finally {
      connecting.value = false;
    }
  }

  async function refreshProjects() {
    if (!sessionId.value) return;
    projectsLoading.value = true;
    projectsError.value = "";
    try {
      const res = await repairSftpProjects(sessionId.value);
      projects.value = Array.isArray(res) ? res : res?.items || [];
      if (!projects.value.length) projectsError.value = "Keine WordPress Roots gefunden.";
    } catch (e: any) {
      projectsError.value = e?.response?.data?.error || e?.response?.data?.msg || e?.message || "Projekt-Suche fehlgeschlagen";
    } finally {
      projectsLoading.value = false;
    }
  }

  async function saveRoot() {
    if (!selectedProject.value) return;
    savingRoot.value = true;
    rootSaved.value = false;
    projectsError.value = "";
    try {
      await repairSetRoot(id, selectedProject.value);
      rootSaved.value = true;
      setTimeout(() => (rootSaved.value = false), 1600);
    } catch (e: any) {
      projectsError.value = e?.response?.data?.error || e?.response?.data?.msg || e?.message || "Root speichern fehlgeschlagen";
    } finally {
      savingRoot.value = false;
    }
  }

  // ---------------------------
  const showAudit = ref(false);
  const actionHistory = ref<any[]>([]);
  const historyBusy = ref(false);
  const lastActionId = ref<string | null>(null);


  async function loadActionHistory() {
    showAudit.value = true;
    historyBusy.value = true;
    try {
      const res = await repairListActions({
        root_path: activeRootPath.value,
        ticket_id: id,
      });
      actionHistory.value = res.items || [];
    } finally {
      historyBusy.value = false;
    }
  }

  async function rollbackAction(action_id: string) {
    const res = await repairRollbackAction({
      action_id,
      session_id: sessionId.value,
    });
    fixResult.value = res;
    await loadActionHistory();
  }


  // Explorer
  // ---------------------------
  const currentPath = ref("/");
  const lsLoading = ref(false);
  const lsError = ref("");
  const items = ref<any[]>([]);
  const showAllInExplorer = ref(false);
  const diagnoseScopePath = ref<string>("");

  const dirs = computed(() => items.value.filter((x: any) => x.type === "dir"));
  const files = computed(() => items.value.filter((x: any) => x.type === "file"));

  const hiddenDirs = new Set([".composer", ".subversion", ".opcache", "logs", "vendor", "~", ".cache", ".ssh", ".git"]);
  const hiddenFilePrefixes = [".bash", ".zsh", ".profile", ".npm", ".composer"];

  const filteredDirs = computed(() => {
    if (showAllInExplorer.value) return dirs.value;
    return dirs.value.filter((d: any) => !hiddenDirs.has(String(d.name || "").trim()));
  });
  const filteredFiles = computed(() => {
    if (showAllInExplorer.value) return files.value;
    return files.value.filter((f: any) => {
      const n = String(f.name || "").trim();
      return !hiddenFilePrefixes.some((p) => n.startsWith(p));
    });
  });

  function join(base: string, name: string) {
    if (base === "/") return "/" + name;
    return base.replace(/\/+$/, "") + "/" + name;
  }
  function goUp() {
    if (currentPath.value === "/") return;
    const p = currentPath.value.replace(/\/+$/, "");
    const idx = p.lastIndexOf("/");
    currentPath.value = idx <= 0 ? "/" : p.slice(0, idx);
    ls(currentPath.value);
  }
  function goToPath(p: string) {
    currentPath.value = p || "/";
    ls(currentPath.value);
  }
  function fixPermsDry(opts?: { dry_run?: boolean }) {
    return fixPerms({ dry_run: opts?.dry_run ?? true });
  }

  async function ls(path: string) {
    if (!sessionId.value) return;
    lsLoading.value = true;
    lsError.value = "";
    try {
      const res = await repairSftpLs(sessionId.value, path);
      if (res?.error) throw new Error(String(res.error));
      items.value = res?.items || [];
    } catch (e: any) {
      lsError.value = e?.response?.data?.error || e?.message || "ls fehlgeschlagen";
      items.value = [];
    } finally {
      lsLoading.value = false;
    }
  }

  function setDiagnoseScope(path: string) {
    diagnoseScopePath.value = path || "";
  }

  function suggestRootFromWpConfig() {
    selectedProject.value = currentPath.value;
  }

  const savingRootFromExplorer = ref(false);
  const canSetRootHere = computed(() => !!sessionId.value && currentPath.value !== "/");

  async function setRootFromExplorer() {
    if (!canSetRootHere.value) return;
    savingRootFromExplorer.value = true;
    projectsError.value = "";
    try {
      await repairSetRoot(id, currentPath.value);
      selectedProject.value = currentPath.value;
    } catch (e: any) {
      projectsError.value = e?.response?.data?.error || e?.response?.data?.msg || e?.message || "Root speichern fehlgeschlagen";
    } finally {
      savingRootFromExplorer.value = false;
    }
  }

  function formatBytes(bytes?: number | null) {
    if (bytes == null) return "";
    const b = Number(bytes);
    if (b < 1024) return `${b} B`;
    const kb = b / 1024;
    if (kb < 1024) return `${kb.toFixed(1)} KB`;
    const mb = kb / 1024;
    return `${mb.toFixed(1)} MB`;
  }

  // aktive Root (SFTP Projekt oder Explorer)
  const activeRootPath = computed(() => {
    if (selectedProject.value) return selectedProject.value;
    if (currentPath.value && currentPath.value !== "/") return currentPath.value;
    return "";
  });

  // ---------------------------
  // Diagnose
  // ---------------------------
  const diagnoseLoading = ref(false);
  const diagnoseError = ref("");
  const diagnoseResult = ref<any>(null);

  async function runDiagnose() {
    diagnoseLoading.value = true;
    diagnoseError.value = "";
    diagnoseResult.value = null;

    const root_path = activeRootPath.value;
    const base_url = baseUrl.value;

    if (!sessionId.value) {
      diagnoseLoading.value = false;
      diagnoseError.value = "Bitte zuerst SFTP verbinden (Session fehlt).";
      return;
    }
    if (!root_path || !base_url || base_url === "#") {
      diagnoseLoading.value = false;
      diagnoseError.value = "Bitte zuerst Root setzen (Projekt wählen) und sicherstellen, dass eine Domain vorhanden ist.";
      return;
    }

    try {
      const res = await repairDiagnose({
        session_id: sessionId.value, // <-- wichtig: session_id (nicht sid)
        root_path,
        base_url,
        verify_ssl: true,
        capture_snippet: true,
        tail_lines: 300,
        redact_logs: true,
      });
      if (res?.error) throw new Error(String(res.error));
      diagnoseResult.value = res;
    } catch (e: any) {
      diagnoseError.value = e?.response?.data?.error || e?.response?.data?.msg || e?.message || "Diagnose fehlgeschlagen";
    } finally {
      diagnoseLoading.value = false;
    }
  }

  // ---------------------------
  // Schnell-Fixes
  // ---------------------------
  const fixBusy = ref("");
  const fixError = ref("");
  const fixResult = ref<any>(null);

  async function runFix(kind: string, fn: () => Promise<any>) {
    fixBusy.value = kind;
    fixError.value = "";
    fixResult.value = null;
    try {
      const r = await fn();
      if (r?.error) throw new Error(String(r.error));
      fixResult.value = r;
    } catch (e: any) {
      fixError.value = e?.response?.data?.error || e?.response?.data?.msg || e?.message || "Fix fehlgeschlagen";
    } finally {
      fixBusy.value = "";
    }
  }

  function fixHtaccess(opts?: { dry_run?: boolean }) {
    const dry_run = opts?.dry_run ?? true;

    return runFix("htaccess", async () => {
      const res = await repairFixHtaccess({
        session_id: sessionId.value,
        root_path: activeRootPath.value,
        ticket_id: id,
        dry_run,
      });

      lastActionId.value = res.action_id || null;
      return res;
    });
  }





  function fixDropins(opts?: { dry_run?: boolean }) {
    const dry_run = opts?.dry_run ?? true;
    return runFix("dropins", () =>
      repairFixDropins({
        session_id: sessionId.value,
        root_path: activeRootPath.value,
        ticket_id: id,
        dry_run,
      })
    );
  }

  function fixPerms(opts?: { dry_run?: boolean }) {
    const dry_run = opts?.dry_run ?? true;
    return runFix("perms", () =>
      repairFixPermissions({
        session_id: sessionId.value,
        root_path: activeRootPath.value,
        dry_run,
        ticket_id: id,
      })
    );
  }
  function fixMaintenance(opts?: { dry_run?: boolean }) {
    const dry_run = opts?.dry_run ?? true;
    return runFix("maint", () =>
      repairFixMaintenance({
        session_id: sessionId.value,
        root_path: activeRootPath.value,
        ticket_id: id,
        dry_run,
      })
    );
  }

  function statusPillClass(raw?: string | null) {
    const s = String(raw || "").toLowerCase();
    if (["open", "offen", "neu", "pending"].includes(s))
      return "bg-amber-100 text-amber-800 dark:bg-amber-500/20 dark:text-amber-200";
    if (["await", "waiting", "wartend", "warten"].includes(s))
      return "bg-sky-100 text-sky-800 dark:bg-sky-500/20 dark:text-sky-200";
    if (["closed", "done", "resolved", "erledigt", "bezahlt", "abgeschlossen"].includes(s))
      return "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-200";
    if (["urgent", "error", "fail", "abgebrochen"].includes(s))
      return "bg-red-100 text-red-800 dark:bg-red-500/20 dark:text-red-200";
    return "bg-gray-100 text-gray-800 dark:bg-white/10 dark:text-gray-100";
  }

  return proxyRefs({
    // route/ticket id
    id,

    // ticket
    ticket,
    ticketLoading,
    ticketError,

    // fields
    sftpHost, sftpUser, sftpPort, sftpPass,
    wpUser, wpPass,
    hostingUrl, hostingUser, hostingPass,
    rootPathHint,

    // helpers
    norm, baseUrl,
    statusPillClass,

    // password ui
    show, copied, copyToClipboard,

    // sftp
    sessionId, connecting, connectError, connectInfo,
    projects, projectsLoading, projectsError,
    selectedProject, connectSftp, refreshProjects,
    savingRoot, rootSaved, saveRoot,

    // explorer
    currentPath, lsLoading, lsError, items,
    showAllInExplorer, filteredDirs, filteredFiles,
    join, ls, goUp, goToPath,
    canSetRootHere, savingRootFromExplorer, setRootFromExplorer,
    diagnoseScopePath, setDiagnoseScope,
    suggestRootFromWpConfig,
    formatBytes,

    // active root / diagnose
    activeRootPath,
    diagnoseLoading, diagnoseError, diagnoseResult,
    runDiagnose,

    // quickfixes
    fixBusy, fixError, fixResult,
    fixHtaccess, fixDropins, fixPermsDry, fixMaintenance,

    showAudit,
    actionHistory,
    historyBusy,
    loadActionHistory,
    rollbackAction,
    lastActionId,
    fixPerms,
  });


}
