// src/modules/wpRepair/fixes/renderFixSummary.ts
import type { FixKey } from "./fixRegistry";

export type SummaryVariant = "ok" | "warn" | "error";

export type SummaryAction = {
  label: string;
  fixKey: FixKey;
  mode: "preview" | "apply";
  // optional: Parameter weiterreichen (z.B. max_files)
  params?: any;
  variant?: "primary" | "secondary";
};

export type FixSummary = {
  title: string;
  message: string;
  badge: string;
  variant: SummaryVariant;
  bullets?: string[];
  aiHint?: string;
  actions?: SummaryAction[];
};

function uniqueActions(actions: SummaryAction[]): SummaryAction[] {
  const seen = new Set<string>();
  const out: SummaryAction[] = [];
  for (const a of actions) {
    const k = `${a.mode}:${a.fixKey}:${a.label}`;
    if (seen.has(k)) continue;
    seen.add(k);
    out.push(a);
  }
  return out;
}

export function renderFixSummary(
  key: FixKey,
  data: any,
  mode: "preview" | "apply"
): FixSummary {
  // ------------- Maintenance -------------
  if (key === "maintenance_remove") {
    const skipped = !!(data?.skipped || data?.result?.skipped);
    const reason = data?.result?.reason || data?.reason || "";
    if (skipped) {
      return {
        title: "Keine Änderung nötig",
        message: reason || ".maintenance nicht vorhanden",
        badge: "SKIPPED",
        variant: "warn",
      };
    }
    return {
      title: "Maintenance entfernt",
      message: "Die Datei .maintenance wurde entfernt (oder bereinigt).",
      badge: mode === "preview" ? "PREVIEW" : "APPLIED",
      variant: "ok",
    };
  }

  // ------------- Permissions -------------
  if (key === "permissions_apply") {
        const changes = data?.changes || data?.changed || data?.result?.changes || data?.result?.changed || [];
    const scanned = data?.scanned ?? data?.result?.scanned;
    const count = Array.isArray(changes) ? changes.length : 0;

    return {
      title: mode === "preview" ? "Würde Permissions ändern" : "Permissions angewendet",
      message:
        count === 0
          ? "Keine Änderungen nötig."
          : `${count} Änderung(en) ${mode === "preview" ? "würden durchgeführt" : "wurden durchgeführt"}.`,
      badge: count === 0 ? "OK" : mode === "preview" ? "PREVIEW" : "APPLIED",
      variant: count === 0 ? "ok" : "warn",
      bullets: [
        ...(typeof scanned === "number" ? [`Geprüft: ${scanned}`] : []),
        ...(count > 0
          ? [
              `${changes[0]?.path} (${changes[0]?.from} → ${changes[0]?.to})`,
              ...(count > 1 ? [`+ ${count - 1} weitere…`] : []),
            ]
          : []),
      ],
      aiHint:
        count > 0
          ? "Nach Apply: wenn WP-Admin oder Plugins Probleme machen, wp-content Schreibrechte und Owner prüfen."
          : "Permissions sind bereits korrekt.",
    };
  }

  // ------------- Dropins -------------
  if (key === "dropins_apply") {
    const items = data?.items || data?.result?.items || [];
    const present = data?.present_count ?? data?.result?.present_count ?? 0;
    const rec = data?.recommended_default_disable || [];
    const risky = data?.risky_requires_explicit || [];

    return {
      title: mode === "preview" ? "Drop-ins Analyse" : "Drop-ins deaktiviert",
      message:
        present === 0
          ? "Keine Drop-ins gefunden."
          : `${present} Drop-in(s) gefunden. ${mode === "preview" ? "Bitte Auswahl prüfen." : "Änderungen wurden durchgeführt."}`,
      badge: present === 0 ? "OK" : mode === "preview" ? "PREVIEW" : "APPLIED",
      variant: present === 0 ? "ok" : "warn",
      bullets: [
        ...(rec.length ? [`Empfohlen: ${rec.join(", ")}`] : []),
        ...(risky.length ? [`Risky (nur explizit): ${risky.join(", ")}`] : []),
        ...(items?.[0]?.name ? [`Beispiel: ${items[0].name} (${items[0].exists ? "vorhanden" : "nicht vorhanden"})`] : []),
      ],
      aiHint:
        present > 0
          ? "Wenn Caching-Probleme bestehen: object-cache.php/advanced-cache.php zuerst deaktivieren; db.php nur wenn nötig."
          : "Kein Handlungsbedarf.",
    };
  }

    // ------------- Core Preview -------------
  if (key === "core_preview") {
    const integrity = data?.integrity || data;
    const counts = integrity?.counts || {};
    const ok = !!integrity?.integrity_ok;

    const unreadableFiles = Array.isArray(integrity?.unreadable_files) ? integrity.unreadable_files : [];
    const changed = Number(counts.changed ?? 0);
    const missing = Number(counts.missing ?? 0);
    const unreadable = Number(counts.unreadable ?? unreadableFiles.length ?? 0);

    const actions: SummaryAction[] = [];

    // Wenn Permission denied/unreadable: zielgerichtet Permissions-Fix anbieten (nur die betroffenen rel_paths)
    if (unreadable > 0 || unreadableFiles.length > 0) {
      const rels = unreadableFiles
        .map((x: any) => String(x?.rel || "").trim())
        .filter(Boolean);

      const rules = rels.length ? { rel_paths: rels } : {};

      actions.push({
        label: "Permissions fixen",
        fixKey: "permissions_apply",
        mode: "apply",
        params: { rules },
        variant: "primary",
      });
      actions.push({
        label: "Permissions Preview",
        fixKey: "permissions_apply",
        mode: "preview",
        params: { rules },
        variant: "secondary",
      });
    }

    // Wenn changed/missing: Core Replace Preview anbieten
    if ((changed > 0 || missing > 0) && !ok) {
      actions.push({
        label: "Core Replace Preview",
        fixKey: "core_replace_apply",
        mode: "preview",
        variant: "secondary",
      });
    }

    return {
      title: "Core Integrity",
      message: ok
        ? "Core scheint intakt."
        : `Integrity nicht OK: changed=${changed}, missing=${missing}, unreadable=${unreadable}`,
      badge: ok ? "OK" : "ISSUES",
      variant: ok ? "ok" : "error",
      bullets: [
        ...(unreadableFiles?.length
          ? [`Unreadable: ${unreadableFiles[0]?.rel || unreadableFiles[0]?.path}`]
          : []),
        ...(integrity?.notes?.length ? [String(integrity.notes[0])] : []),
      ],
      aiHint: ok
        ? "Keine Aktion nötig."
        : unreadable > 0
          ? "Erst Permissions fixen (unreadable), danach Core Replace Preview prüfen und nur geplante Files ersetzen."
          : "Core Replace Preview prüfen und nur geplante Files ersetzen.",
      actions: uniqueActions(actions),
    };
  }

// ------------- Core Replace -------------
  if (key === "core_replace_apply") {
    const planCount = data?.plan_count ?? data?.result?.plan_count ?? 0;
    const deniedCount = data?.denied_count ?? data?.result?.denied_count ?? 0;
    const wpVersion = data?.wp_version ?? data?.result?.wp_version;

    const actions: SummaryAction[] = [];
    // Wenn Plan da ist: Apply anbieten (aber du hast ohnehin Apply-Button)
    if (mode === "preview" && planCount > 0) {
      actions.push({
        label: "Core Replace Apply",
        fixKey: "core_replace_apply",
        mode: "apply",
        variant: "primary",
      });
    }

    return {
      title: mode === "preview" ? "Core Replace Plan" : "Core Replace gestartet",
      message:
        planCount === 0
          ? "Kein Replace nötig."
          : `${planCount} Datei(en) im Plan. ${deniedCount ? `${deniedCount} blockiert durch Policy.` : ""}`.trim(),
      badge: planCount === 0 ? "OK" : mode === "preview" ? "PREVIEW" : "APPLIED",
      variant: planCount === 0 ? "ok" : "warn",
      bullets: [
        ...(wpVersion ? [`WP Version: ${wpVersion}`] : []),
        ...(planCount > 0 && data?.plan?.[0]?.rel ? [`Beispiel: ${data.plan[0].rel}`] : []),
        ...(planCount > 1 ? [`+ ${planCount - 1} weitere…`] : []),
      ],
      aiHint:
        planCount > 0
          ? "Vor Apply: erst Core Preview vollständig laufen lassen (max_files erhöhen). Apply nur, wenn Core wirklich betroffen ist."
          : "Kein Handlungsbedarf.",
      actions: uniqueActions(actions),
    };
  }

  return {
    title: "Ergebnis",
    message: "Details im JSON.",
    badge: mode === "preview" ? "PREVIEW" : "APPLIED",
    variant: "ok",
  };
}
