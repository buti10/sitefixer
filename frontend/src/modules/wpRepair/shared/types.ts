// src/modules/wpRepair/shared/types.ts
export type FixKey = string;
export type FixRisk = "low" | "medium" | "high";

export type ActionStartResponse = {
  ok: boolean;
  action_id?: string;
  error?: string;
  [k: string]: any;
};

export type FixDef = {
  key: FixKey;
  backendFixId: string;

  title: string;
  description: string;
  risk: FixRisk;

  isAction: boolean;

  preview?: (sessionId: string, params?: any) => Promise<any>;
  run: (sessionId: string, params?: any) => Promise<any>;

  ui?: {
    hasPreview?: boolean;
    icon?: string;
    paramsHint?: string;
    runLabel?: string;
    previewLabel?: string;
  };
};
