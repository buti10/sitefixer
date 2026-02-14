// src/modules/wpRepair/stores/wpRepair.store.ts
import { defineStore } from "pinia";
import {
  startSession,
  sftpConnect,
  listProjects,
  selectProject,
  findWpRoot,
  selectWpRoot,
  runDiagnose,

  getActionStatus,
  getActionFindings,

  fixMaintenanceRemove,
  permissionsApply,
  dropinsApply,

  corePreview,
  coreReplacePreview,
  coreReplaceApply,

  type SftpProjectItem,
} from "../api/wpRepair";

import { getFix, type FixKey } from "../fixes/fixRegistry";

type StepKey = "connect" | "diagnose" | "quickfix" | "history";
type ActionStartResponse = { ok: boolean; action_id?: string; error?: string };

function findingsToLines(findings: any[]): string[] {
  if (!Array.isArray(findings) || findings.length === 0) return [];
  return findings.map((f) => {
    const ts = f?.ts || f?.time || f?.created_at || "";
    const level = (f?.level || f?.severity || f?.kind || "").toString().toUpperCase();
    const msg = f?.message || f?.text || f?.title || f?.code || "";
    const line = [ts, level, msg].filter(Boolean).join(" · ").trim();
    return line || JSON.stringify(f);
  });
}

// Terminal Status: backend nutzt bei dir u.a. "applied"
function isTerminalStatus(s?: string | null) {
  if (!s) return false;
  const v = String(s).toLowerCase();
  return [
    "done",
    "ok",
    "applied",
    "partial",
    "failed",
    "error",
    "canceled",
    "cancelled",
    "skipped",
  ].includes(v);
}

// Status/Action normalisieren: { ok:true, action:{...} } ODER {status:'applied', ...}
function extractActionObject(actionStatus: any) {
  return actionStatus?.action ?? actionStatus ?? null;
}

function extractActionStatusValue(actionStatus: any): string {
  const a = extractActionObject(actionStatus);
  return (
    a?.status ??
    a?.meta?.status ??
    actionStatus?.status ??
    actionStatus?.meta?.status ??
    ""
  ).toString();
}

function extractFindingsArray(findingsResp: any): any[] {
  const items = findingsResp?.items ?? findingsResp?.findings ?? [];
  return Array.isArray(items) ? items : [];
}

export const useWpRepairStore = defineStore("wpRepair", {
  state: () => ({
    ticketId: 0 as number,
    ticket: null as any,

    sessionId: null as string | null,

    projectItems: [] as SftpProjectItem[],
    selectedProjectRoot: "" as string,

    wpRoot: "" as string,
    wpRootCandidates: [] as Array<any>,

    connectionOk: false as boolean,

    diagnose: {
      summary: null as any,
      findings: [] as any[],
      lastRunAt: null as string | null,
    },

    quickfix: {
      corePreview: null as any,
      coreReplacePreview: null as any,
      dropinsPreview: null as any,
    },

    // per-Fix Preview Cache (damit Recommendations "Preview" auf andere Cards wirken können)
    previewCache: {} as Record<string, any>,

    activeStep: "connect" as StepKey,

    runningActionId: null as string | null,

    // raw response vom backend (kann {ok,action} sein)
    actionStatus: null as any,
    actionLogs: [] as string[],

    loading: false as boolean,
    error: null as string | null,
  }),

  getters: {
    projects(state) {
      return state.projectItems || [];
    },
    canDiagnose(state) {
      return !!state.sessionId && state.connectionOk && !!state.wpRoot;
    },
    canFix(state) {
      return !!state.sessionId && !!state.selectedProjectRoot && !!state.wpRoot;
    },
    isRunning(state) {
      return !!state.runningActionId;
    },

    // NEU: Status als string (für FixCard)
    actionStatusValue(state): string {
      return extractActionStatusValue(state.actionStatus) || "idle";
    },

    // NEU: Action Objekt direkt (falls UI mehr Details braucht)
    actionObject(state): any {
      return extractActionObject(state.actionStatus);
    },
  },

  actions: {
    resetForTicket(ticketId: number) {
      this.ticketId = ticketId;
      this.ticket = null;

      this.sessionId = null;

      this.projectItems = [];
      this.selectedProjectRoot = "";

      this.wpRoot = "";
      this.wpRootCandidates = [];

      this.connectionOk = false;

      this.diagnose = { summary: null, findings: [], lastRunAt: null };
      this.quickfix = { corePreview: null, coreReplacePreview: null, dropinsPreview: null };
      this.previewCache = {};

      this.activeStep = "connect";

      this.runningActionId = null;

      this.runningFixKey = null;
      this.lastCompletedFixKey = null;
      this.lastCompletedAction = null;

      this.actionStatus = null;
      this.actionLogs = [];

      this.loading = false;
      this.error = null;
    },

    setTicket(ticket: any) {
      this.ticket = ticket;
      const id = Number(ticket?.ticket_id || ticket?.id || 0);
      if (id) this.ticketId = id;
    },

    async connectAndLoadProjects() {
      this.loading = true;
      this.error = null;

      try {
        if (!this.ticket) throw new Error("Ticketdaten fehlen (store.ticket ist leer).");

        const sess = await startSession(this.ticket);
        if (!sess?.ok || !sess?.session_id) {
          throw new Error(sess?.error || "Session konnte nicht gestartet werden.");
        }
        this.sessionId = sess.session_id;

        // Backend: /sftp/connect statt /session/test
        try {
          const t = await sftpConnect(this.sessionId);
          this.connectionOk = !!t?.ok;
          if (!t?.ok) {
            this.error = (t as any)?.error || (t as any)?.message || "SFTP Connect fehlgeschlagen.";
          }
        } catch {
          // wenn Endpoint nicht existiert: trotzdem weiter
          this.connectionOk = true;
        }

        const pr = await listProjects(this.sessionId);
        this.projectItems = Array.isArray(pr?.items) ? pr.items! : [];
        if (!this.projectItems.length) throw new Error(pr?.error || "Keine Projekte gefunden.");

        if (!this.selectedProjectRoot) this.selectedProjectRoot = this.projectItems[0].root_path;

        await this.setProjectRoot(this.selectedProjectRoot);
      } catch (e: any) {
        this.error = e?.response?.data?.error || e?.message || "Verbindung fehlgeschlagen";
        this.connectionOk = false;
      } finally {
        this.loading = false;
      }
    },

    async setProjectRoot(projectRoot: string) {
      if (!this.sessionId) {
        this.error = "Keine Session vorhanden.";
        return;
      }

      this.loading = true;
      this.error = null;

      try {
        const pr = (projectRoot || "").trim();
        if (!pr) throw new Error("Bitte Projekt wählen.");

        const res = await selectProject(this.sessionId, pr);
        if (!res?.ok) throw new Error(res?.error || "Projekt konnte nicht gesetzt werden.");

        this.selectedProjectRoot = pr;

        // UX default
        this.wpRoot = pr;

        const s2 = await selectWpRoot(this.sessionId, pr);
        if (!s2?.ok) throw new Error(s2?.error || "WP-Root konnte nicht gesetzt werden.");

        this.wpRootCandidates = [];
      } catch (e: any) {
        this.error = e?.response?.data?.error || e?.message || "Projekt setzen fehlgeschlagen";
      } finally {
        this.loading = false;
      }
    },

    async detectAndSetWpRoot(maxDepth = 5) {
      if (!this.sessionId) {
        this.error = "Keine Session vorhanden.";
        return;
      }
      if (!this.selectedProjectRoot) {
        this.error = "Bitte zuerst ein Projekt auswählen.";
        return;
      }

      this.loading = true;
      this.error = null;

      try {
        const sel = await selectProject(this.sessionId, this.selectedProjectRoot);
        if (!sel?.ok) throw new Error(sel?.error || "Projekt konnte nicht gesetzt werden.");

        const r = await findWpRoot(this.sessionId, maxDepth);
        if (!r?.ok) throw new Error(r?.error || "WP-Root Suche fehlgeschlagen.");

        this.wpRootCandidates = r?.candidates || [];
        const best = r?.wp_root || this.wpRootCandidates?.[0]?.wp_root;
        if (!best) throw new Error("WP-Root konnte nicht erkannt werden.");

        const s2 = await selectWpRoot(this.sessionId, best);
        if (!s2?.ok) throw new Error(s2?.error || "WP-Root konnte nicht gesetzt werden.");

        this.wpRoot = best;
        this.connectionOk = true;
      } catch (e: any) {
        this.error = e?.response?.data?.error || e?.message || "WP-Root Erkennung fehlgeschlagen";
      } finally {
        this.loading = false;
      }
    },

    async setRootManually(wpRoot: string) {
      if (!this.sessionId) {
        this.error = "Keine Session vorhanden.";
        return;
      }
      if (!this.selectedProjectRoot) {
        this.error = "Bitte zuerst ein Projekt auswählen.";
        return;
      }

      this.loading = true;
      this.error = null;

      try {
        const p = (wpRoot || "").trim();
        if (!p) throw new Error("WP-Root ist leer.");

        const sel = await selectProject(this.sessionId, this.selectedProjectRoot);
        if (!sel?.ok) throw new Error(sel?.error || "Projekt konnte nicht gesetzt werden.");

        const res = await selectWpRoot(this.sessionId, p);
        if (!res?.ok) throw new Error(res?.error || "WP-Root konnte nicht gesetzt werden.");

        this.wpRoot = p;
        this.connectionOk = true;
      } catch (e: any) {
        this.error = e?.response?.data?.error || e?.message || "WP-Root setzen fehlgeschlagen";
      } finally {
        this.loading = false;
      }
    },

    async runDiagnose() {
      if (!this.canDiagnose) {
        this.error = "Bitte zuerst verbinden, Projekt wählen und WP-Root setzen.";
        this.activeStep = "connect";
        return;
      }

      this.loading = true;
      this.error = null;

      try {
        const sel = await selectProject(this.sessionId!, this.selectedProjectRoot);
        if (!sel?.ok) throw new Error(sel?.error || "Projekt konnte nicht gesetzt werden.");

        const s2 = await selectWpRoot(this.sessionId!, this.wpRoot);
        if (!s2?.ok) throw new Error(s2?.error || "WP-Root konnte nicht gesetzt werden.");

        const res = await runDiagnose(this.sessionId!);
        const diag = (res as any)?.diagnose || null;

        this.diagnose.summary = diag;
        this.diagnose.findings = (res as any)?.findings || [];
        this.diagnose.lastRunAt = new Date().toISOString();
      } catch (e: any) {
        this.error = e?.response?.data?.error || e?.message || "Diagnose fehlgeschlagen";
      } finally {
        this.loading = false;
      }
    },

    // ---------------- Polling ----------------
    async startPollingAction(actionId: string, fixKey: FixKey) {
      this.runningActionId = actionId;
      this.runningFixKey = fixKey;
      this.actionStatus = null;
      this.actionLogs = [];
      this.error = null;

      let consecutiveErrors = 0;

      const poll = async () => {
        if (!this.runningActionId) return;

        try {
          const statusResp = await getActionStatus(actionId);

          // WICHTIG: wir speichern raw, aber Status wird über Getter sauber gelesen
          this.actionStatus = statusResp;

          // Live-Logs
          try {
            const fResp = await getActionFindings(actionId);
            const findings = extractFindingsArray(fResp);
            const lines = findingsToLines(findings);
            if (lines.length) this.actionLogs = lines;
          } catch {
            // ignore
          }

          consecutiveErrors = 0;

          const st = extractActionStatusValue(this.actionStatus);

          if (isTerminalStatus(st)) {
            // Optional: SKIPPED/partial reason anzeigen, falls keine Findings
            const a = extractActionObject(this.actionStatus);
            const reason = a?.result?.reason || a?.meta?.notes || a?.error || "";

            if ((st || "").toLowerCase() === "skipped" && !this.actionLogs?.length) {
              this.actionLogs = [reason ? `SKIPPED · ${reason}` : "SKIPPED"];
              this.error = null;
            }

            const aDone = extractActionObject(this.actionStatus);

            this.lastCompletedFixKey = fixKey;
            this.lastCompletedAction = aDone;

            this.runningActionId = null;
            this.runningFixKey = null;
            return;
          }
        } catch (e: any) {
          consecutiveErrors++;

          const httpStatus = e?.response?.status;
          if (httpStatus === 404) {
            this.error = "Polling 404: Action nicht gefunden. UI freigegeben.";
            this.runningActionId = null;
            this.runningFixKey = null;
            return;
          }

          if (consecutiveErrors >= 5) {
            this.error = "Polling fehlgeschlagen (mehrfach). UI freigegeben.";
            this.runningActionId = null;
            this.runningFixKey = null;
            return;
          }
        }

        setTimeout(poll, 1200);
      };

      poll();
    },

    async runAction(fixKey: FixKey, startFn: () => Promise<ActionStartResponse>) {
      if (!this.canFix) {
        this.error = "Bitte zuerst Projekt + WP-Root setzen.";
        this.activeStep = "connect";
        return null;
      }

      this.loading = true;
      this.error = null;

      try {
        const sel = await selectProject(this.sessionId!, this.selectedProjectRoot);
        if (!sel?.ok) throw new Error(sel?.error || "Projekt konnte nicht gesetzt werden.");

        const s2 = await selectWpRoot(this.sessionId!, this.wpRoot);
        if (!s2?.ok) throw new Error(s2?.error || "WP-Root konnte nicht gesetzt werden.");

        const res: any = await startFn();
        if (!res?.ok || !res?.action_id) throw new Error(res?.error || "Action konnte nicht gestartet werden.");

        await this.startPollingAction(res.action_id, fixKey);

        // WICHTIG: damit FixCard lastResult setzen kann
        return res;
      } catch (e: any) {
        this.error = e?.response?.data?.error || e?.message || "Action fehlgeschlagen";
        return null;
      } finally {
        this.loading = false;
      }
    },

    // ---------------- Fixes ----------------
    async runFix(key: FixKey, params?: any) {
      const fix = getFix(key);

      if (fix.isAction) {
        return await this.runAction(() => fix.run(this.sessionId!, params) as any);
      }

      if (!this.canFix) {
        this.error = "Bitte zuerst Projekt + WP-Root setzen.";
        this.activeStep = "connect";
        return null;
      }

      this.loading = true;
      this.error = null;

      try {
        const sel = await selectProject(this.sessionId!, this.selectedProjectRoot);
        if (!sel?.ok) throw new Error(sel?.error || "Projekt konnte nicht gesetzt werden.");

        const s2 = await selectWpRoot(this.sessionId!, this.wpRoot);
        if (!s2?.ok) throw new Error(s2?.error || "WP-Root konnte nicht gesetzt werden.");

        const data = await fix.run(this.sessionId!, params);

        if (key === "core_preview") this.quickfix.corePreview = data;

        return data;
      } catch (e: any) {
        this.error = e?.response?.data?.error || e?.message || "Fix fehlgeschlagen";
        return null;
      } finally {
        this.loading = false;
      }
    },

    async previewFix(key: FixKey, params?: any) {
      const fix = getFix(key);
      if (!fix.preview) return null;

      if (!this.canFix) {
        this.error = "Bitte zuerst Projekt + WP-Root setzen.";
        this.activeStep = "connect";
        return null;
      }

      this.loading = true;
      this.error = null;

      try {
        const sel = await selectProject(this.sessionId!, this.selectedProjectRoot);
        if (!sel?.ok) throw new Error(sel?.error || "Projekt konnte nicht gesetzt werden.");

        const s2 = await selectWpRoot(this.sessionId!, this.wpRoot);
        if (!s2?.ok) throw new Error(s2?.error || "WP-Root konnte nicht gesetzt werden.");

        const data = await fix.preview(this.sessionId!, params);
        this.previewCache[key] = data;

        if (key === "core_replace_apply") this.quickfix.coreReplacePreview = data;
        if (key === "dropins_apply") this.quickfix.dropinsPreview = data;

        return data;
      } catch (e: any) {
        this.error = e?.response?.data?.error || e?.message || "Preview fehlgeschlagen";
        return null;
      } finally {
        this.loading = false;
      }
    },

    // ---------------- Legacy wrappers (können bleiben) ----------------
    async doMaintenanceRemove() {
      return await this.runAction(() => fixMaintenanceRemove(this.sessionId!));
    },

    async doPermissionsApply(rules?: any) {
      // erlaubt künftig gezielte Regeln
      return await this.runAction(() => permissionsApply(this.sessionId!, { rules: rules || {} } as any));
    },

    async doDropinsApply(disableNames: string[]) {
      return await this.runAction(() => dropinsApply(this.sessionId!, disableNames));
    },

    // ---------------- Core ----------------
    async loadCorePreview(maxFiles = 500) {
      if (!this.canFix) {
        this.error = "Bitte zuerst Projekt + WP-Root setzen.";
        return;
      }

      this.loading = true;
      this.error = null;

      try {
        const sel = await selectProject(this.sessionId!, this.selectedProjectRoot);
        if (!sel?.ok) throw new Error(sel?.error || "Projekt konnte nicht gesetzt werden.");

        const s2 = await selectWpRoot(this.sessionId!, this.wpRoot);
        if (!s2?.ok) throw new Error(s2?.error || "WP-Root konnte nicht gesetzt werden.");

        this.quickfix.corePreview = await corePreview(this.sessionId!, maxFiles);
      } catch (e: any) {
        this.error = e?.response?.data?.error || e?.message || "Core Preview fehlgeschlagen";
      } finally {
        this.loading = false;
      }
    },

    async loadCoreReplacePreview(opts?: any) {
      if (!this.canFix) {
        this.error = "Bitte zuerst Projekt + WP-Root setzen.";
        return;
      }

      this.loading = true;
      this.error = null;

      try {
        const sel = await selectProject(this.sessionId!, this.selectedProjectRoot);
        if (!sel?.ok) throw new Error(sel?.error || "Projekt konnte nicht gesetzt werden.");

        const s2 = await selectWpRoot(this.sessionId!, this.wpRoot);
        if (!s2?.ok) throw new Error(s2?.error || "WP-Root konnte nicht gesetzt werden.");

        this.quickfix.coreReplacePreview = await coreReplacePreview(this.sessionId!, opts || {});
      } catch (e: any) {
        this.error = e?.response?.data?.error || e?.message || "Core Replace Preview fehlgeschlagen";
      } finally {
        this.loading = false;
      }
    },

    async applyCoreReplace(opts?: any) {
      return await this.runAction(() => coreReplaceApply(this.sessionId!, opts || {}));
    },

    goStep(step: StepKey) {
      if (step === "diagnose" && !this.canDiagnose) {
        this.activeStep = "connect";
        return;
      }
      if (step === "quickfix" && !this.canFix) {
        this.activeStep = "connect";
        return;
      }
      this.activeStep = step;
    },
  },
});
