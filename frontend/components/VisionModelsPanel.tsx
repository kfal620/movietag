import { useEffect, useState } from "react";
import type { VisionPipeline, PipelinesResponse } from "../lib/types";

type Props = {
  authToken?: string;
};

export function VisionModelsPanel({ authToken }: Props) {
  const [pipelines, setPipelines] = useState<VisionPipeline[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [warming, setWarming] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    let interval: number | undefined;

    const fetchStatus = async () => {
      try {
        const response = await fetch("/api/vision/pipelines", {
          headers: authToken ? { Authorization: `Bearer ${authToken}` } : undefined,
        });
        if (!response.ok) {
          const detail = await response.text();
          throw new Error(detail || "Unable to load pipeline status.");
        }
        const payload = (await response.json()) as PipelinesResponse;
        if (mounted) {
          setPipelines(payload.pipelines ?? []);
          setError(null);
        }
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err.message : "Unable to load pipeline status.");
        }
      }
    };

    void fetchStatus();
    interval = window.setInterval(fetchStatus, 8000);
    return () => {
      mounted = false;
      if (interval) {
        window.clearInterval(interval);
      }
    };
  }, [authToken]);

  const warmupModels = async () => {
    if (!authToken) {
      setError("Provide a moderator or admin token to warm up models.");
      return;
    }
    setWarming(true);
    setStatusMessage(null);
    setError(null);
    try {
      const response = await fetch("/api/models/vision/warmup", {
        method: "POST",
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || "Warmup failed.");
      }
      setStatusMessage("Warmup queued. Models should report as loaded shortly.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Warmup failed.");
    } finally {
      setWarming(false);
    }
  };

  const needsWarmup = pipelines.some((pipeline) => !pipeline.loaded);

  return (
    <section className="settings-card" aria-live="polite">
      <div className="settings-card__header">
        <div>
          <p className="eyebrow">Vision Pipelines</p>
          <h3 style={{ margin: "0.1rem 0 0.35rem" }}>Available Models</h3>
          <p className="muted">
            Status refreshes every few seconds. Select different pipelines for standard or enhanced analysis.
          </p>
        </div>
        {needsWarmup ? <span className="pill">Needs warmup</span> : <span className="pill pill--primary">Ready</span>}
      </div>

      <div className="settings-card__body">
        {pipelines.length ? (
          <ul className="list">
            {pipelines.map((pipeline) => (
              <li key={pipeline.id} className="list__item">
                <div>
                  <strong>{pipeline.name}</strong>
                  <div className="muted" style={{ marginTop: 4 }}>
                    Model: {pipeline.model_id} · Device: {pipeline.device} · Resolution: {pipeline.input_resolution}px
                  </div>
                  {pipeline.version ? (
                    <div className="muted" style={{ fontSize: "0.85rem" }}>
                      Version: {pipeline.version}
                    </div>
                  ) : null}
                  <div style={{ marginTop: 6 }}>
                    <span style={{ fontSize: "0.85rem", color: pipeline.loaded ? "var(--success)" : "var(--muted)" }}>
                      {pipeline.loaded ? "✓ Loaded and ready" : "○ Not loaded yet"}
                    </span>
                  </div>
                </div>
                <span className={`chip ${pipeline.loaded ? "chip--success" : "chip--muted"}`}>
                  {pipeline.loaded ? "Loaded" : "Not loaded"}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No vision pipelines reported yet.</p>
        )}
      </div>

      <div className="settings-card__footer">
        <div>
          {statusMessage ? <p style={{ color: "var(--success)", margin: "0.4rem 0 0" }}>{statusMessage}</p> : null}
          {error ? <p style={{ color: "var(--danger)", margin: "0.4rem 0 0" }}>{error}</p> : null}
        </div>
        <button className="button button--primary" onClick={warmupModels} disabled={!needsWarmup || warming}>
          {warming ? "Warming up..." : "Load / warm up models"}
        </button>
      </div>
    </section>
  );
}
