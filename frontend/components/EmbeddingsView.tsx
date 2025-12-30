"use client";

import { useState, useEffect } from "react";
import useSWR from "swr";
import { FrameEmbeddingInfo, PrototypeInfo } from "../lib/types";

type Props = {
    authToken?: string;
};

type EmbeddingListItem = FrameEmbeddingInfo & {
    frame?: {
        id: number;
        movie_title?: string | null;
        status: string;
    };
};

type EmbeddingsResponse = {
    items: EmbeddingListItem[];
    total: number;
    limit: number;
    offset: number;
};

type PrototypesResponse = {
    prototypes: Array<{
        attribute: string;
        value: string;
        count: number;
        frame_ids: number[];
    }>;
    total: number;
};

const fetcher = async (url: string, token?: string) => {
    const response = await fetch(url, {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    });
    if (!response.ok) {
        throw new Error(`Request failed (${response.status})`);
    }
    return response.json();
};

export function EmbeddingsView({ authToken }: Props) {
    const [selectedPipeline, setSelectedPipeline] = useState<string | null>(null);
    const [selectedAttribute, setSelectedAttribute] = useState<string | null>(null);
    const [deletingId, setDeletingId] = useState<number | null>(null);
    const [bulkDeleteFrameId, setBulkDeleteFrameId] = useState<number | null>(null);
    const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

    const { data: embeddingsData, mutate: mutateEmbeddings } = useSWR<EmbeddingsResponse>(
        ["/api/embeddings?limit=100", authToken],
        ([url, token]: [string, string]) => fetcher(url, token),
        { revalidateOnFocus: false }
    );

    const { data: prototypesData } = useSWR<PrototypesResponse>(
        ["/api/embeddings/verified-attributes", authToken],
        ([url, token]: [string, string]) => fetcher(url, token),
        { revalidateOnFocus: false }
    );

    const handleDelete = async (frameId: number, pipelineId: string, embeddingId: number) => {
        if (!authToken) {
            setMessage({ type: "error", text: "Authentication required" });
            return;
        }

        if (!confirm(`Delete embedding for pipeline "${pipelineId}"? This will revert to default if available.`)) {
            return;
        }

        setDeletingId(embeddingId);
        setMessage(null);

        try {
            const response = await fetch(`/api/embeddings/frames/${frameId}/embeddings/${pipelineId}`, {
                method: "DELETE",
                headers: {
                    Authorization: `Bearer ${authToken}`,
                },
            });

            if (!response.ok) {
                throw new Error(await response.text());
            }

            const result = await response.json();

            await mutateEmbeddings();

            if (result.warning) {
                setMessage({ type: "error", text: result.warning });
            } else if (result.reverted) {
                setMessage({ type: "success", text: `Reverted to default ${pipelineId} embedding` });
            } else {
                setMessage({ type: "success", text: "Embedding deleted" });
            }
        } catch (error) {
            setMessage({
                type: "error",
                text: error instanceof Error ? error.message : "Delete failed",
            });
        } finally {
            setDeletingId(null);
        }
    };

    const handleBulkDelete = async (frameId: number) => {
        if (!authToken) {
            setMessage({ type: "error", text: "Authentication required" });
            return;
        }

        if (!confirm(`Delete ALL embeddings for frame #${frameId}? This cannot be undone and will require re-analysis.`)) {
            return;
        }

        setBulkDeleteFrameId(frameId);
        setMessage(null);

        try {
            const response = await fetch(`/api/embeddings/frames/${frameId}/embeddings`, {
                method: "DELETE",
                headers: {
                    Authorization: `Bearer ${authToken}`,
                },
            });

            if (!response.ok) {
                throw new Error(await response.text());
            }

            const result = await response.json();

            await mutateEmbeddings();
            setMessage({ type: "error", text: result.warning || "All embeddings deleted" });
        } catch (error) {
            setMessage({
                type: "error",
                text: error instanceof Error ? error.message : "Bulk delete failed",
            });
        } finally {
            setBulkDeleteFrameId(null);
        }
    };

    const embeddings = embeddingsData?.items ?? [];
    const prototypes = prototypesData?.prototypes ?? [];

    // Group embeddings by frame
    const embeddingsByFrame = embeddings.reduce((acc, emb) => {
        const frameId = emb.frame?.id ?? emb.frameId ?? 0;
        if (!acc[frameId]) {
            acc[frameId] = [];
        }
        acc[frameId].push(emb);
        return acc;
    }, {} as Record<number, EmbeddingListItem[]>);

    // Filter prototypes
    const filteredPrototypes = prototypes.filter((p) => {
        if (selectedAttribute && p.attribute !== selectedAttribute) return false;
        return true;
    });

    // Get unique attributes for filter
    const uniqueAttributes = Array.from(new Set(prototypes.map((p) => p.attribute)));

    return (
        <section className="panel" style={{ padding: "1.5rem", height: "100%" }}>
            <div style={{ marginBottom: "1.5rem" }}>
                <h2 style={{ margin: 0, marginBottom: "0.5rem" }}>Image Embeddings</h2>
                <p className="muted" style={{ margin: 0 }}>
                    Manage frame embeddings and view visual prototypes from verified attributes
                </p>
            </div>

            {message && (
                <div
                    style={{
                        padding: "0.75rem",
                        marginBottom: "1rem",
                        borderRadius: "8px",
                        background: message.type === "success" ? "var(--success-bg)" : "var(--danger-bg)",
                        color: message.type === "success" ? "var(--success)" : "var(--danger)",
                        border: `1px solid ${message.type === "success" ? "var(--success)" : "var(--danger)"}`,
                    }}
                >
                    {message.text}
                </div>
            )}

            <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "1.5rem", height: "calc(100% - 100px)" }}>
                {/* Embeddings Table */}
                <div style={{ display: "flex", flexDirection: "column", minHeight: 0 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                        <h3 style={{ margin: 0 }}>Embeddings ({embeddingsData?.total ?? 0})</h3>
                        <select
                            className="select"
                            value={selectedPipeline ?? ""}
                            onChange={(e) => setSelectedPipeline(e.target.value || null)}
                            style={{ width: "200px" }}
                        >
                            <option value="">All Pipelines</option>
                            {Array.from(new Set(embeddings.map((e) => e.pipelineId))).map((pipeline) => (
                                <option key={pipeline} value={pipeline}>
                                    {pipeline}
                                </option>
                            ))}
                        </select>
                    </div>

                    <div style={{ flex: 1, overflowY: "auto", border: "1px solid var(--border)", borderRadius: "8px" }}>
                        <table style={{ width: "100%", borderCollapse: "collapse" }}>
                            <thead style={{ position: "sticky", top: 0, background: "var(--surface)", zIndex: 1 }}>
                                <tr>
                                    <th style={{ padding: "0.75rem", textAlign: "left", borderBottom: "1px solid var(--border)" }}>Frame</th>
                                    <th style={{ padding: "0.75rem", textAlign: "left", borderBottom: "1px solid var(--border)" }}>Pipeline</th>
                                    <th style={{ padding: "0.75rem", textAlign: "center", borderBottom: "1px solid var(--border)" }}>Dimension</th>
                                    <th style={{ padding: "0.75rem", textAlign: "center", borderBottom: "1px solid var(--border)" }}>Count</th>
                                    <th style={{ padding: "0.75rem", textAlign: "right", borderBottom: "1px solid var(--border)" }}>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {Object.entries(embeddingsByFrame)
                                    .filter(([, frameEmbs]) =>
                                        !selectedPipeline || frameEmbs.some((e) => e.pipelineId === selectedPipeline)
                                    )
                                    .map(([frameId, frameEmbs]) => {
                                        const displayEmbs = selectedPipeline
                                            ? frameEmbs.filter((e) => e.pipelineId === selectedPipeline)
                                            : frameEmbs;

                                        return displayEmbs.map((emb, idx) => (
                                            <tr key={emb.id} style={{ borderBottom: "1px solid var(--border)" }}>
                                                {idx === 0 && (
                                                    <td
                                                        rowSpan={displayEmbs.length}
                                                        style={{ padding: "0.75rem", verticalAlign: "top" }}
                                                    >
                                                        <div>
                                                            <div style={{ fontWeight: 500 }}>Frame #{frameId}</div>
                                                            <div className="muted" style={{ fontSize: "0.85rem" }}>
                                                                {emb.frame?.movie_title || "Unknown"}
                                                            </div>
                                                        </div>
                                                    </td>
                                                )}
                                                <td style={{ padding: "0.75rem" }}>
                                                    <code style={{ fontSize: "0.85rem" }}>{emb.pipelineId}</code>
                                                </td>
                                                <td style={{ padding: "0.75rem", textAlign: "center" }}>{emb.dimension}</td>
                                                {idx === 0 && (
                                                    <td
                                                        rowSpan={displayEmbs.length}
                                                        style={{ padding: "0.75rem", textAlign: "center", verticalAlign: "top" }}
                                                    >
                                                        {frameEmbs.length}
                                                    </td>
                                                )}
                                                {idx === 0 && (
                                                    <td
                                                        rowSpan={displayEmbs.length}
                                                        style={{ padding: "0.75rem", textAlign: "right", verticalAlign: "top" }}
                                                    >
                                                        <div style={{ display: "flex", gap: "0.5rem", justifyContent: "flex-end" }}>
                                                            <button
                                                                className="button button--ghost"
                                                                onClick={() => handleDelete(Number(frameId), emb.pipelineId, emb.id)}
                                                                disabled={deletingId === emb.id}
                                                                style={{ fontSize: "0.85rem", padding: "0.25rem 0.5rem", color: "var(--danger)" }}
                                                            >
                                                                {deletingId === emb.id ? "..." : "Delete"}
                                                            </button>
                                                            {frameEmbs.length > 1 && (
                                                                <button
                                                                    className="button button--ghost"
                                                                    onClick={() => handleBulkDelete(Number(frameId))}
                                                                    disabled={bulkDeleteFrameId === Number(frameId)}
                                                                    style={{ fontSize: "0.85rem", padding: "0.25rem 0.5rem", color: "var(--danger)" }}
                                                                    title="Delete all embeddings for this frame"
                                                                >
                                                                    {bulkDeleteFrameId === Number(frameId) ? "..." : "Delete All"}
                                                                </button>
                                                            )}
                                                        </div>
                                                    </td>
                                                )}
                                            </tr>
                                        ));
                                    })}
                            </tbody>
                        </table>

                        {embeddings.length === 0 && (
                            <div style={{ padding: "2rem", textAlign: "center", color: "var(--muted)" }}>
                                No embeddings found. Analyze frames to generate embeddings.
                            </div>
                        )}
                    </div>
                </div>

                {/* Verified Attributes Panel */}
                <div style={{ display: "flex", flexDirection: "column", minHeight: 0 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                        <h3 style={{ margin: 0 }}>Verified Attributes ({filteredPrototypes.length})</h3>
                        <select
                            className="select"
                            value={selectedAttribute ?? ""}
                            onChange={(e) => setSelectedAttribute(e.target.value || null)}
                            style={{ width: "150px" }}
                        >
                            <option value="">All Types</option>
                            {uniqueAttributes.map((attr) => (
                                <option key={attr} value={attr}>
                                    {attr}
                                </option>
                            ))}
                        </select>
                    </div>

                    <div style={{ flex: 1, overflowY: "auto", border: "1px solid var(--border)", borderRadius: "8px", padding: "1rem" }}>
                        {filteredPrototypes.length === 0 ? (
                            <div style={{ textAlign: "center", color: "var(--muted)", padding: "2rem 0" }}>
                                No verified attributes found. Edit and verify attributes in frames to build prototypes.
                            </div>
                        ) : (
                            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                                {filteredPrototypes.map((proto, idx) => (
                                    <div
                                        key={idx}
                                        style={{
                                            padding: "0.75rem",
                                            border: "1px solid var(--border)",
                                            borderRadius: "6px",
                                            background: "var(--surface)",
                                        }}
                                    >
                                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start", marginBottom: "0.5rem" }}>
                                            <div>
                                                <div style={{ fontSize: "0.85rem", color: "var(--muted)", marginBottom: "0.25rem" }}>
                                                    {proto.attribute}
                                                </div>
                                                <div style={{ fontWeight: 500 }}>{proto.value}</div>
                                            </div>
                                            <span
                                                style={{
                                                    padding: "0.25rem 0.5rem",
                                                    borderRadius: "4px",
                                                    background: "var(--success-bg)",
                                                    color: "var(--success)",
                                                    fontSize: "0.85rem",
                                                    fontWeight: 500,
                                                }}
                                            >
                                                {proto.count} examples
                                            </span>
                                        </div>
                                        <div style={{ fontSize: "0.85rem", color: "var(--muted)" }}>
                                            Frames: {proto.frame_ids.slice(0, 5).join(", ")}
                                            {proto.frame_ids.length > 5 && ` +${proto.frame_ids.length - 5} more`}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </section>
    );
}
