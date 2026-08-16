import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import {
  CheckCircle2,
  Clock3,
  Loader2,
  RefreshCw,
  XCircle,
} from "lucide-react";
import { api } from "@/lib/api";

type RunStep = {
  stage_name: string;
  step_name: string;
  step_type: string;
  status: string;
  log_ref?: string | null;
};

type PipelineRun = {
  id: string;
  pipeline_id: string;
  run_number: number;
  status: string;
  created_at?: number;
  started_at?: number;
  finished_at?: number;
  current_step?: number;
  approval_step?: number | null;
  steps?: RunStep[];
};

export const Route = createFileRoute("/cicd/runs")({
  component: CicdRunsPage,
});

function CicdRunsPage() {
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<PipelineRun | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionBusy, setActionBusy] = useState(false);
  const [logContent, setLogContent] = useState("");
  const [error, setError] = useState<string | null>(null);

  const params = new URLSearchParams(window.location.search);
  const requestedRunId = params.get("run_id");

  const loadRuns = async () => {
    setLoading(true);
    setError(null);

    try {
      const result = await api<{ runs: PipelineRun[] }>(
        "GET",
        "/api/cicd/runs"
      );

      const list = result.runs ?? [];
      setRuns(list);

      if (requestedRunId) {
        const requested = list.find((r) => r.id === requestedRunId);

        if (requested) {
          await loadRun(requested.id);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load runs");
    } finally {
      setLoading(false);
    }
  };

  const loadRun = async (runId: string) => {
    try {
      const result = await api<{ run: PipelineRun }>(
        "GET",
        `/api/cicd/runs/${runId}`
      );

      setSelectedRun(result.run);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load run");
    }
  };

  useEffect(() => {
    loadRuns();
  }, []);

  useEffect(() => {
    if (!selectedRun) return;

    if (
      selectedRun.status === "RUNNING" ||
      selectedRun.status === "QUEUED" ||
      selectedRun.status === "WAITING_APPROVAL"
    ) {
      const timer = window.setInterval(() => {
        loadRun(selectedRun.id);
      }, 3000);

      return () => window.clearInterval(timer);
    }
  }, [selectedRun?.id, selectedRun?.status]);

  const approve = async () => {
    if (!selectedRun) return;

    setActionBusy(true);

    try {
      await api(
        "POST",
        `/api/cicd/runs/${selectedRun.id}/approve`,
        {
          approved_by: "opensible-ui",
        }
      );

      await loadRun(selectedRun.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approval failed");
    } finally {
      setActionBusy(false);
    }
  };

  const reject = async () => {
    if (!selectedRun) return;

    setActionBusy(true);

    try {
      await api(
        "POST",
        `/api/cicd/runs/${selectedRun.id}/reject`,
        {
          rejected_by: "opensible-ui",
          reason: "Rejected from OpenSible UI",
        }
      );

      await loadRun(selectedRun.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reject failed");
    } finally {
      setActionBusy(false);
    }
  };

  const loadStepLog = async (index: number) => {
    if (!selectedRun) return;

    try {
      const result = await api<{ content: string }>(
        "GET",
        `/api/cicd/runs/${selectedRun.id}/steps/${index}/log`
      );

      setLogContent(result.content ?? "");
    } catch (err) {
      setLogContent(
        err instanceof Error ? err.message : "Unable to load log"
      );
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">CI/CD Run History</h1>
          <p className="text-sm text-[var(--color-muted-foreground)] mt-1">
            Monitor OpenTofu and Ansible pipeline executions.
          </p>
        </div>

        <button
          onClick={loadRuns}
          className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm"
        >
          <RefreshCw className="h-4 w-4" />
          Refresh
        </button>
      </div>

      {error && (
        <div className="rounded-md border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-500">
          {error}
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-[340px_1fr]">
        <div className="rounded-lg border overflow-hidden">
          {loading && runs.length === 0 ? (
            <div className="p-4 text-sm">Loading runs...</div>
          ) : runs.length === 0 ? (
            <div className="p-4 text-sm text-[var(--color-muted-foreground)]">
              No pipeline runs found.
            </div>
          ) : (
            runs.map((run) => (
              <button
                key={run.id}
                onClick={() => loadRun(run.id)}
                className="w-full text-left border-b last:border-b-0 p-4 hover:bg-[var(--color-muted)]"
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="font-medium">
                    Run #{run.run_number}
                  </span>

                  <StatusBadge status={run.status} />
                </div>

                <div className="text-xs mt-1 text-[var(--color-muted-foreground)] break-all">
                  {run.id}
                </div>
              </button>
            ))
          )}
        </div>

        <div className="space-y-5">
          {!selectedRun ? (
            <div className="rounded-lg border p-8 text-center text-sm text-[var(--color-muted-foreground)]">
              Select a pipeline run.
            </div>
          ) : (
            <>
              <div className="rounded-lg border p-5">
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <div>
                    <h2 className="font-semibold text-lg">
                      Run #{selectedRun.run_number}
                    </h2>
                    <div className="text-sm text-[var(--color-muted-foreground)]">
                      {selectedRun.id}
                    </div>
                  </div>

                  <StatusBadge status={selectedRun.status} />
                </div>

                {selectedRun.status === "WAITING_APPROVAL" && (
                  <div className="mt-5 rounded-lg border border-yellow-500/30 bg-yellow-500/10 p-4">
                    <div className="font-medium">
                      Manual approval required
                    </div>

                    <div className="text-sm text-[var(--color-muted-foreground)] mt-1">
                      Review the OpenTofu plan before continuing.
                    </div>

                    <div className="flex gap-3 mt-4">
                      <button
                        onClick={reject}
                        disabled={actionBusy}
                        className="rounded-md border border-red-500 px-4 py-2 text-sm text-red-500"
                      >
                        Reject
                      </button>

                      <button
                        onClick={approve}
                        disabled={actionBusy}
                        className="rounded-md bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-[var(--color-primary-foreground)]"
                      >
                        Approve & Continue
                      </button>
                    </div>
                  </div>
                )}
              </div>

              <div className="rounded-lg border p-5">
                <h3 className="font-semibold mb-4">Pipeline stages</h3>

                <div className="space-y-3">
                  {(selectedRun.steps ?? []).map((step, index) => (
                    <button
                      key={`${step.stage_name}-${index}`}
                      onClick={() => loadStepLog(index)}
                      className="w-full flex items-center justify-between rounded-md border px-4 py-3 text-left hover:bg-[var(--color-muted)]"
                    >
                      <div>
                        <div className="font-medium">
                          {step.stage_name}
                        </div>
                        <div className="text-xs text-[var(--color-muted-foreground)]">
                          {step.step_name}
                        </div>
                      </div>

                      <StatusBadge status={step.status} />
                    </button>
                  ))}
                </div>
              </div>

              {logContent && (
                <div className="rounded-lg border overflow-hidden">
                  <div className="border-b px-4 py-3 font-medium">
                    Step log
                  </div>

                  <pre className="p-4 max-h-[500px] overflow-auto text-xs whitespace-pre-wrap bg-black/80 text-white">
                    {logContent}
                  </pre>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const value = String(status || "").toUpperCase();

  if (value === "SUCCESS") {
    return (
      <span className="inline-flex items-center gap-1 text-sm text-green-500">
        <CheckCircle2 className="h-4 w-4" />
        SUCCESS
      </span>
    );
  }

  if (value === "FAILED" || value === "REJECTED") {
    return (
      <span className="inline-flex items-center gap-1 text-sm text-red-500">
        <XCircle className="h-4 w-4" />
        {value}
      </span>
    );
  }

  if (value === "RUNNING" || value === "QUEUED") {
    return (
      <span className="inline-flex items-center gap-1 text-sm">
        <Loader2 className="h-4 w-4 animate-spin" />
        {value}
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1 text-sm text-yellow-500">
      <Clock3 className="h-4 w-4" />
      {value}
    </span>
  );
}
