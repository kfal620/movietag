import { useState } from "react";
import { Frame } from "../lib/types";

type Props = {
    frame: Frame;
    onClose: () => void;
};

type PredictionDebugInfo = {
    label: string;
    clip_score: number;
    prototype_score: number | null;
    prototype_count: number;
    final_score: number;
};

type AttributeLog = {
    selected?: PredictionDebugInfo;
    candidates?: PredictionDebugInfo[];
};

export function AnalysisLogModal({ frame, onClose }: Props) {
    const log = frame.analysisLog || {};
    const attributes = Object.keys(log).sort();
    const [expandedAttr, setExpandedAttr] = useState<string | null>(null);

    return (
        <div
            style={{
                position: "fixed",
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                background: "rgba(0, 0, 0, 0.5)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                zIndex: 1100, // Higher than FrameEditModal
                padding: "2rem",
            }}
            onClick={onClose}
        >
            <div
                style={{
                    background: "var(--panel)",
                    border: "1px solid var(--border)",
                    borderRadius: "12px",
                    width: "100%",
                    maxWidth: "800px",
                    maxHeight: "80vh",
                    display: "flex", // Keep this flex
                    flexDirection: "column", // Stack children vertically
                    boxShadow: "0 4px 24px rgba(0,0,0,0.3)",
                }}
                onClick={(e) => e.stopPropagation()}
            >
                <div style={{ padding: "1.5rem", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <h3 style={{ margin: 0 }}>Vision Analysis Log</h3>
                    <button className="button button--ghost" onClick={onClose}>Close</button>
                </div>

                <div style={{ overflowY: "auto", padding: "1.5rem", flex: 1 }}> {/* Ensure this section takes remaining space and scrolls */}
                    {attributes.length === 0 ? (
                        <p className="muted">No detailed analysis log available for this frame.</p>
                    ) : (
                        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                            {attributes.map((attr) => {
                                const entry = log[attr];
                                // Handle case where entry might be a list (multi-label) but basic logic handles object
                                // We'll assume structure from backend: { selected: ..., candidates: [] }
                                // If it's a list (from multi-label handling in tasks.py), we might need to iterate.
                                // For now, let's assuming single entry for simplicity or just first one if it's a list.

                                let data: AttributeLog | null = null;
                                if (Array.isArray(entry)) {
                                    data = entry[0] as AttributeLog;
                                } else {
                                    data = entry as AttributeLog;
                                }

                                if (!data) return null;

                                const isExpanded = expandedAttr === attr;
                                const winner = data.selected;

                                return (
                                    <div key={attr} style={{ border: "1px solid var(--border)", borderRadius: "8px", overflow: "hidden" }}>
                                        <div
                                            style={{
                                                padding: "1rem",
                                                background: "var(--surface)",
                                                cursor: "pointer",
                                                display: "flex",
                                                justifyContent: "space-between",
                                                alignItems: "center"
                                            }}
                                            onClick={() => setExpandedAttr(isExpanded ? null : attr)}
                                        >
                                            <div>
                                                <strong>{attr}</strong>
                                                {winner && (
                                                    <span className="muted" style={{ marginLeft: "0.5rem" }}>
                                                        → {winner.label} ({Math.round(winner.final_score * 100)}%)
                                                    </span>
                                                )}
                                            </div>
                                            <div style={{ fontSize: "0.8rem", color: "var(--muted)" }}>
                                                {isExpanded ? "Hide Details" : "Show Details"}
                                            </div>
                                        </div>

                                        {isExpanded && data.candidates && (
                                            <div style={{ padding: "1rem", borderTop: "1px solid var(--border)" }}>
                                                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
                                                    <thead>
                                                        <tr style={{ textAlign: "left", color: "var(--muted)" }}>
                                                            <th style={{ paddingBottom: "0.5rem" }}>Label</th>
                                                            <th style={{ paddingBottom: "0.5rem" }}>CLIP Score</th>
                                                            <th style={{ paddingBottom: "0.5rem" }}>Proto Score</th>
                                                            <th style={{ paddingBottom: "0.5rem" }}>Proto Count</th>
                                                            <th style={{ paddingBottom: "0.5rem" }}>Final</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        {data.candidates.map((c, idx) => {
                                                            const isWinner = c.label === winner?.label;
                                                            return (
                                                                <tr key={idx} style={{ background: isWinner ? "rgba(59, 130, 246, 0.1)" : undefined }}>
                                                                    <td style={{ padding: "0.25rem 0", fontWeight: isWinner ? "bold" : "normal" }}>{c.label}</td>
                                                                    <td style={{ padding: "0.25rem 0" }}>{(c.clip_score).toFixed(3)}</td>
                                                                    <td style={{ padding: "0.25rem 0" }}>{c.prototype_score !== null ? c.prototype_score.toFixed(3) : "-"}</td>
                                                                    <td style={{ padding: "0.25rem 0" }}>{c.prototype_count > 0 ? c.prototype_count : "-"}</td>
                                                                    <td style={{ padding: "0.25rem 0", fontWeight: "bold" }}>{(c.final_score).toFixed(3)}</td>
                                                                </tr>
                                                            );
                                                        })}
                                                    </tbody>
                                                </table>
                                                <div style={{ marginTop: "0.5rem", fontSize: "0.8rem", color: "var(--muted)" }}>
                                                    Formula: 60% CLIP + 40% Prototype (if available)
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
