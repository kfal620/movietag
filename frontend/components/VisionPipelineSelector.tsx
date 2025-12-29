import { useState, useEffect } from "react";
import type { VisionPipeline, PipelinesResponse } from "../lib/types";

type Props = {
    value: string;
    onChange: (pipelineId: string) => void;
    authToken?: string;
};

export function VisionPipelineSelector({ value, onChange, authToken }: Props) {
    const [pipelines, setPipelines] = useState<VisionPipeline[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchPipelines = async () => {
            try {
                const response = await fetch("/api/vision/pipelines", {
                    headers: authToken ? { Authorization: `Bearer ${authToken}` } : undefined,
                });

                if (!response.ok) {
                    throw new Error("Failed to fetch pipelines");
                }

                const data = (await response.json()) as PipelinesResponse;
                setPipelines(data.pipelines || []);
                setError(null);
            } catch (err) {
                setError(err instanceof Error ? err.message : "Failed to load pipelines");
            } finally {
                setLoading(false);
            }
        };

        void fetchPipelines();
    }, [authToken]);

    if (loading) {
        return (
            <div className="muted" style={{ fontSize: "0.9rem" }}>
                Loading pipelines...
            </div>
        );
    }

    if (error) {
        return (
            <div style={{ color: "var(--danger)", fontSize: "0.9rem" }}>
                {error}
            </div>
        );
    }

    if (pipelines.length === 0) {
        return (
            <div className="muted" style={{ fontSize: "0.9rem" }}>
                No pipelines available
            </div>
        );
    }

    return (
        <div style={{ marginBottom: "1rem" }}>
            <label htmlFor="pipeline-selector" style={{ display: "block", marginBottom: "0.5rem", fontWeight: 500 }}>
                Vision Pipeline
            </label>
            <select
                id="pipeline-selector"
                value={value}
                onChange={(e) => onChange(e.target.value)}
                style={{
                    width: "100%",
                    padding: "0.5rem",
                    borderRadius: "4px",
                    border: "1px solid var(--border-color, #ddd)",
                    backgroundColor: "var(--bg-secondary, #f8f9fa)",
                    fontSize: "0.95rem",
                }}
            >
                {pipelines.map((pipeline) => (
                    <option key={pipeline.id} value={pipeline.id}>
                        {pipeline.name}
                        {!pipeline.loaded && " (not loaded)"}
                        {pipeline.device && ` - ${pipeline.device.toUpperCase()}`}
                    </option>
                ))}
            </select>

            {pipelines.find((p) => p.id === value) && (
                <div className="muted" style={{ marginTop: "0.5rem", fontSize: "0.85rem" }}>
                    {(() => {
                        const selected = pipelines.find((p) => p.id === value);
                        if (!selected) return null;
                        return (
                            <>
                                Model: {selected.model_id} · Device: {selected.device}
                                {selected.loaded ? " · ✓ Loaded" : " · ⚠ Not loaded yet"}
                            </>
                        );
                    })()}
                </div>
            )}
        </div>
    );
}
