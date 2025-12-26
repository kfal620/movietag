import { useEffect, useState } from "react";

type VisionModelStatus = {
  id: string;
  name: string;
  loaded: boolean;
  available: boolean;
  device: string;
  version?: string | null;
  last_loaded_at?: string | null;
  error?: string | null;
};

type VisionStatusResponse = { models: VisionModelStatus[] };

type Props = {
  authToken?: string;
};

export function VisionModelsPanel({ authToken }: Props) {
  const [models, setModels] = useState<VisionModelStatus[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [warming, setWarming] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    let interval: number | undefined;

    const fetchStatus = async () => {
      try {
        const response = await fetch("/api/models/vision/status", {
          headers: authToken ? { Authorization: `Bearer ${authToken}` } : undefined,
        });
        if (!response.ok) {
          const detail = await response.text();
          throw new Error(detail || "Unable to load model status.");
        }
        const payload = (await response.json()) as VisionStatusResponse;
        if (mounted) {
          setModels(payload.models ?? []);
          setError(null);
        }
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err.message : "Unable to load model status.");
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

  const needsWarmup = models.some((model) => model.available && !model.loaded);

  return (
    <section className="settings-card" aria-live="polite">
      <div className="settings-card__header">
        <div>
          <p className="eyebrow">Vision models</p>
          <h3 style={{ margin: "0.1rem 0 0.35rem" }}>Live model readiness</h3>
          <p className="muted">
            Status refreshes every few seconds to show what is loaded and ready for inference.
          </p>
        </div>
        {needsWarmup ? <span className="pill">Needs warmup</span> : <span className="pill pill--primary">Ready</span>}
      </div>

      <div className="settings-card__body">
        {models.length ? (
          <ul className="list">
            {models.map((model) => (
              <li key={model.id} className="list__item">
                <div>
                  <strong>{model.name}</strong>
                  <div className="muted" style={{ marginTop: 4 }}>
                    Device: {model.device || "unknown"} · Version: {model.version || "—"}
                  </div>
                  {model.last_loaded_at ? (
                    <div className="muted">Last loaded: {new Date(model.last_loaded_at).toLocaleString()}</div>
                  ) : null}
                  {model.error ? <div style={{ color: "var(--danger)" }}>Error: {model.error}</div> : null}
                </div>
                <span className={`chip ${model.loaded ? "chip--success" : "chip--muted"}`}>
                  {model.loaded ? "Loaded" : model.available ? "Not loaded" : "Unavailable"}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No vision models reported yet.</p>
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
