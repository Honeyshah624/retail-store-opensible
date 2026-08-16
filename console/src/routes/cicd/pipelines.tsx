import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { GitBranch, Play, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";

type PipelineStep = {
  name: string;
  type: string;
  config?: Record<string, unknown>;
};

type PipelineStage = {
  name: string;
  steps: PipelineStep[];
};

type Pipeline = {
  id: string;
  name: string;
  project_id: string;
  git_repo?: string;
  git_branch?: string;
  stages?: PipelineStage[];
};

export const Route = createFileRoute("/cicd/pipelines")({
  component: CicdPipelinesPage,
});

function CicdPipelinesPage() {
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [loading, setLoading] = useState(false);
  const [triggeringId, setTriggeringId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadPipelines = async () => {
    setLoading(true);
    setError(null);

    try {
      const result = await api<{ pipelines: Pipeline[] }>(
        "GET",
        "/api/cicd/pipelines"
      );

      setPipelines(result.pipelines ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load pipelines");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPipelines();
  }, []);

  const triggerPipeline = async (pipeline: Pipeline) => {
    setTriggeringId(pipeline.id);
    setError(null);

    try {
      const result = await api<{
        success: boolean;
        run_id: string;
        run_number?: number;
      }>(
        "POST",
        `/api/cicd/pipelines/${pipeline.id}/trigger`,
        {
          trigger_type: "manual",
          triggered_by: "opensible-ui",
        }
      );

      if (result.run_id) {
        window.location.href = `/cicd/runs?run_id=${encodeURIComponent(
          result.run_id
        )}`;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to trigger pipeline");
    } finally {
      setTriggeringId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">CI/CD Pipelines</h1>
          <p className="text-sm text-[var(--color-muted-foreground)] mt-1">
            Run OpenTofu, approval, and Ansible deployment workflows.
          </p>
        </div>

        <button
          onClick={loadPipelines}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm hover:bg-[var(--color-muted)]"
        >
          <RefreshCw
            className={`h-4 w-4 ${loading ? "animate-spin" : ""}`}
          />
          Refresh
        </button>
      </div>

      {error && (
        <div className="rounded-md border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-500">
          {error}
        </div>
      )}

      {loading && pipelines.length === 0 ? (
        <div className="text-sm text-[var(--color-muted-foreground)]">
          Loading pipelines...
        </div>
      ) : pipelines.length === 0 ? (
        <div className="rounded-lg border p-8 text-center">
          <GitBranch className="h-8 w-8 mx-auto mb-3 opacity-60" />
          <div className="font-medium">No CI/CD pipelines found</div>
          <p className="text-sm text-[var(--color-muted-foreground)] mt-1">
            Pipelines created for the current project will appear here.
          </p>
        </div>
      ) : (
        <div className="grid gap-4">
          {pipelines.map((pipeline) => (
            <div
              key={pipeline.id}
              className="rounded-lg border bg-[var(--color-card)] p-5"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <GitBranch className="h-5 w-5" />
                    <h2 className="font-semibold text-lg">
                      {pipeline.name}
                    </h2>
                  </div>

                  {pipeline.git_repo && (
                    <div className="mt-2 text-sm text-[var(--color-muted-foreground)] break-all">
                      Repository: {pipeline.git_repo}
                    </div>
                  )}

                  {pipeline.git_branch && (
                    <div className="text-sm text-[var(--color-muted-foreground)]">
                      Branch: {pipeline.git_branch}
                    </div>
                  )}
                </div>

                <button
                  onClick={() => triggerPipeline(pipeline)}
                  disabled={triggeringId === pipeline.id}
                  className="inline-flex items-center gap-2 rounded-md bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-[var(--color-primary-foreground)] disabled:opacity-50"
                >
                  <Play className="h-4 w-4" />
                  {triggeringId === pipeline.id
                    ? "Starting..."
                    : "Run Pipeline"}
                </button>
              </div>

              {pipeline.stages && pipeline.stages.length > 0 && (
                <div className="mt-5 border-t pt-4">
                  <div className="text-xs font-semibold uppercase tracking-wide text-[var(--color-muted-foreground)] mb-3">
                    Pipeline stages
                  </div>

                  <div className="flex flex-wrap gap-2">
                    {pipeline.stages.map((stage, index) => (
                      <div
                        key={`${pipeline.id}-${stage.name}-${index}`}
                        className="rounded-md border px-3 py-2 text-sm"
                      >
                        {index + 1}. {stage.name}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
