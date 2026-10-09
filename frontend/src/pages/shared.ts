import type { RunListItem, SystemInfo } from "../lib/api";

export interface PageProps {
  system: SystemInfo | null;
  runs: RunListItem[];
  refreshRuns: () => Promise<RunListItem[]>;
  refreshSystem: () => Promise<void>;
  activeRunId: string | null;
  selectRun: (runId: string | null) => void;
  systemError: string | null;
  onNavigate: (page: string, param?: string) => void;
}

export function runThumbnail(run: RunListItem): string | null {
  const hasPreview = run.artifacts?.some((a) => a.kind === "preview_png" || a.kind === "orthomosaic_preview");
  const produced = (run.output as { produced?: boolean })?.produced;
  if (!hasPreview && !produced) return null;
  return `/api/runs/${run.run_id}/preview.png`;
}
