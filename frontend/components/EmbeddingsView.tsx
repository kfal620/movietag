"use client";

import { useState, useMemo } from "react";
import useSWR from "swr";

type Props = {
    authToken?: string;
};

type SceneAttributeItem = {
    id: number;
    frame_id: number;
    attribute: string;
    value: string;
    confidence: number | null;
    is_verified: boolean;
    created_at: string | null;
    updated_at: string | null;
    frame?: {
        id: number;
        movie_title?: string | null;
        status: string;
    };
};

type SceneAttributesResponse = {
    items: SceneAttributeItem[];
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
    const [verifiedOnly, setVerifiedOnly] = useState(false);
    const [selectedAttribute, setSelectedAttribute] = useState<string | null>(null);
    const [expandedFrames, setExpandedFrames] = useState<Set<number>>(new Set());
    const [deletingId, setDeletingId] = useState<number | null>(null);
    const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

    const { data: attributesData, mutate: mutateAttributes } = useSWR<SceneAttributesResponse>(
        [`/api/embeddings/scene-attributes?limit=500&verified_only=${verifiedOnly}${selectedAttribute ? `&attribute=${selectedAttribute}` : ''}`, authToken],
        ([url, token]: [string, string]) => fetcher(url, token),
        { revalidateOnFocus: false }
    );

    const { data: prototypesData } = useSWR<PrototypesResponse>(
        ["/api/embeddings/verified-attributes", authToken],
        ([url, token]: [string, string]) => fetcher(url, token),
        { revalidateOnFocus: false }
    );

    const handleDelete = async (attributeId: number, attrName: string, attrValue: string) => {
        if (!authToken) {
            setMessage({ type: "error", text: "Authentication required" });
            return;
        }

        if (!confirm(`Delete "${attrName}: ${attrValue}"? This will remove this attribute value.`)) {
            return;
        }

        setDeletingId(attributeId);
        setMessage(null);

        try {
            const response = await fetch(`/api/embeddings/scene-attributes/${attributeId}`, {
                method: "DELETE",
                headers: {
                    Authorization: `Bearer ${authToken}`,
                },
            });

            if (!response.ok) {
                throw new Error(await response.text());
            }

            const result = await response.json();

            await mutateAttributes();

            setMessage({
                type: "success",
                text: `Deleted ${result.attribute}: ${result.value}${result.was_verified ? " (was user-verified)" : ""}`
            });
        } catch (error) {
            setMessage({
                type: "error",
                text: error instanceof Error ? error.message : "Delete failed",
            });
        } finally {
            setDeletingId(null);
        }
    };

    const toggleFrame = (frameId: number) => {
        setExpandedFrames((prev) => {
            const next = new Set(prev);
            if (next.has(frameId)) {
                next.delete(frameId);
            } else {
                next.add(frameId);
            }
            return next;
        });
    };

    const attributes = attributesData?.items ?? [];
    const prototypes = prototypesData?.prototypes ?? [];

    // Group attributes by frame
    const attributesByFrame = useMemo(() => {
        const grouped: Record<number, SceneAttributeItem[]> = {};
        attributes.forEach((attr) => {
            if (!grouped[attr.frame_id]) {
                grouped[attr.frame_id] = [];
            }
            grouped[attr.frame_id].push(attr);
        });
        return grouped;
    }, [attributes]);

    const frameIds = Object.keys(attributesByFrame).map(Number).sort((a, b) => b - a);

    // Get unique attribute types
    const uniqueAttributeTypes = Array.from(new Set(attributes.map((a) => a.attribute))).sort();

    // Filter prototypes by selected attribute
    const filteredPrototypes = prototypes.filter((p) => {
        if (selectedAttribute && p.attribute !== selectedAttribute) return false;
        return true;
    });

    return (
        <section className="panel" style={{ padding: "1.5rem", height: "100%" }}>
            <div style={{ marginBottom: "1.5rem" }}>
                <h2 style={{ margin: 0, marginBottom: "0.5rem" }}>Scene Attributes & Prototypes</h2>
                <p className="muted" style={{ margin: 0 }}>
                    View all scene attribute values, see which were user-edited, and manage visual prototypes
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
                {/* Scene Attributes Table */}
                <div style={{ display: "flex", flexDirection: "column", minHeight: 0 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem", gap: "1rem", flexWrap: "wrap" }}>
                        <h3 style={{ margin: 0 }}>
                            Frames ({frameIds.length}) · Attributes ({attributes.length})
                        </h3>
                        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                            <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
                                <input
                                    type="checkbox"
                                    checked={verifiedOnly}
                                    onChange={(e) => setVerifiedOnly(e.target.checked)}
                                />
                                <span style={{ fontSize: "0.9rem" }}>User-verified only</span>
                            </label>
                            <select
                                className="select"
                                value={selectedAttribute ?? ""}
                                onChange={(e) => setSelectedAttribute(e.target.value || null)}
                                style={{ width: "180px" }}
                            >
                                <option value="">All Attribute Types</option>
                                {uniqueAttributeTypes.map((attr) => (
                                    <option key={attr} value={attr}>
                                        {attr}
                                    </option>
                                ))}
                            </select>
                        </div>
                    </div>

                    <div style={{ flex: 1, overflowY: "auto", border: "1px solid var(--border)", borderRadius: "8px" }}>
                        <table style={{ width: "100%", borderCollapse: "collapse" }}>
                            <thead style={{ position: "sticky", top: 0, background: "var(--surface)", zIndex: 1 }}>
                                <tr>
                                    <th style={{ padding: "0.75rem", textAlign: "left", borderBottom: "1px solid var(--border)" }}>Frame / Attribute</th>
                                    <th style={{ padding: "0.75rem", textAlign: "left", borderBottom: "1px solid var(--border)" }}>Value</th>
                                    <th style={{ padding: "0.75rem", textAlign: "center", borderBottom: "1px solid var(--border)" }}>Confidence</th>
                                    <th style={{ padding: "0.75rem", textAlign: "center", borderBottom: "1px solid var(--border)" }}>Source</th>
                                    <th style={{ padding: "0.75rem", textAlign: "right", borderBottom: "1px solid var(--border)" }}>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {frameIds.map((frameId) => {
                                    const frameAttrs = attributesByFrame[frameId];
                                    const isExpanded = expandedFrames.has(frameId);
                                    const firstAttr = frameAttrs[0];
                                    const verifiedCount = frameAttrs.filter((a) => a.is_verified).length;

                                    return (
                                        <>
                                            {/* Frame Header Row */}
                                            <tr
                                                key={`frame-${frameId}`}
                                                style={{
                                                    borderBottom: "1px solid var(--border)",
                                                    background: "var(--surface)",
                                                    cursor: "pointer",
                                                }}
                                                onClick={() => toggleFrame(frameId)}
                                            >
                                                <td style={{ padding: "0.75rem" }}>
                                                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                                                        <span style={{ fontSize: "1rem" }}>{isExpanded ? "▼" : "▶"}</span>
                                                        <div>
                                                            <div style={{ fontWeight: 600 }}>Frame #{frameId}</div>
                                                            {firstAttr.frame?.movie_title && (
                                                                <div className="muted" style={{ fontSize: "0.8rem" }}>
                                                                    {firstAttr.frame.movie_title}
                                                                </div>
                                                            )}
                                                        </div>
                                                    </div>
                                                </td>
                                                <td style={{ padding: "0.75rem" }} colSpan={2}>
                                                    <span className="muted" style={{ fontSize: "0.9rem" }}>
                                                        {frameAttrs.length} attribute{frameAttrs.length !== 1 ? "s" : ""}
                                                    </span>
                                                </td>
                                                <td style={{ padding: "0.75rem", textAlign: "center" }}>
                                                    {verifiedCount > 0 && (
                                                        <span
                                                            style={{
                                                                padding: "0.25rem 0.5rem",
                                                                borderRadius: "4px",
                                                                background: "var(--success-bg)",
                                                                color: "var(--success)",
                                                                fontSize: "0.75rem",
                                                                fontWeight: 500,
                                                            }}
                                                        >
                                                            {verifiedCount} verified
                                                        </span>
                                                    )}
                                                </td>
                                                <td></td>
                                            </tr>

                                            {/* Attribute Rows (when expanded) */}
                                            {isExpanded &&
                                                frameAttrs.map((attr) => (
                                                    <tr
                                                        key={attr.id}
                                                        style={{
                                                            borderBottom: "1px solid var(--border)",
                                                            background: attr.is_verified
                                                                ? "rgba(var(--success-rgb, 34, 197, 94), 0.05)"
                                                                : "transparent",
                                                        }}
                                                    >
                                                        <td style={{ padding: "0.75rem", paddingLeft: "3rem" }}>
                                                            <code
                                                                style={{
                                                                    fontSize: "0.85rem",
                                                                    background: "var(--surface)",
                                                                    padding: "0.25rem 0.5rem",
                                                                    borderRadius: "4px",
                                                                }}
                                                            >
                                                                {attr.attribute}
                                                            </code>
                                                        </td>
                                                        <td style={{ padding: "0.75rem" }}>
                                                            <div style={{ fontWeight: 500 }}>{attr.value}</div>
                                                        </td>
                                                        <td style={{ padding: "0.75rem", textAlign: "center" }}>
                                                            {attr.confidence !== null ? (
                                                                <span
                                                                    style={{
                                                                        fontFamily: "monospace",
                                                                        fontSize: "0.85rem",
                                                                        color:
                                                                            attr.confidence > 0.8
                                                                                ? "var(--success)"
                                                                                : attr.confidence > 0.5
                                                                                    ? "var(--warning)"
                                                                                    : "var(--muted)",
                                                                    }}
                                                                >
                                                                    {(attr.confidence * 100).toFixed(1)}%
                                                                </span>
                                                            ) : (
                                                                <span className="muted">—</span>
                                                            )}
                                                        </td>
                                                        <td style={{ padding: "0.75rem", textAlign: "center" }}>
                                                            {attr.is_verified ? (
                                                                <span
                                                                    style={{
                                                                        padding: "0.25rem 0.5rem",
                                                                        borderRadius: "4px",
                                                                        background: "var(--success-bg)",
                                                                        color: "var(--success)",
                                                                        fontSize: "0.75rem",
                                                                        fontWeight: 500,
                                                                    }}
                                                                >
                                                                    ✓ User
                                                                </span>
                                                            ) : (
                                                                <span
                                                                    style={{
                                                                        padding: "0.25rem 0.5rem",
                                                                        borderRadius: "4px",
                                                                        background: "var(--surface)",
                                                                        color: "var(--muted)",
                                                                        fontSize: "0.75rem",
                                                                    }}
                                                                >
                                                                    AI
                                                                </span>
                                                            )}
                                                        </td>
                                                        <td style={{ padding: "0.75rem", textAlign: "right" }}>
                                                            <button
                                                                className="button button--ghost"
                                                                onClick={(e) => {
                                                                    e.stopPropagation();
                                                                    handleDelete(attr.id, attr.attribute, attr.value);
                                                                }}
                                                                disabled={deletingId === attr.id}
                                                                style={{
                                                                    fontSize: "0.85rem",
                                                                    padding: "0.25rem 0.75rem",
                                                                    color: "var(--danger)",
                                                                }}
                                                                title={`Delete this ${attr.attribute} value`}
                                                            >
                                                                {deletingId === attr.id ? "Deleting..." : "Delete"}
                                                            </button>
                                                        </td>
                                                    </tr>
                                                ))}
                                        </>
                                    );
                                })}
                            </tbody>
                        </table>

                        {frameIds.length === 0 && (
                            <div style={{ padding: "2rem", textAlign: "center", color: "var(--muted)" }}>
                                {verifiedOnly
                                    ? "No user-verified attributes found. Edit scene attributes in frames to mark them as verified."
                                    : "No scene attributes found. Analyze frames to generate attributes."}
                            </div>
                        )}
                    </div>
                </div>

                {/* Prototypes Panel */}
                <div style={{ display: "flex", flexDirection: "column", minHeight: 0 }}>
                    <div style={{ marginBottom: "1rem" }}>
                        <h3 style={{ margin: 0, marginBottom: "0.25rem" }}>Visual Prototypes ({filteredPrototypes.length})</h3>
                        <p className="muted" style={{ margin: 0, fontSize: "0.85rem" }}>
                            User-verified attributes used for few-shot learning
                        </p>
                    </div>

                    <div style={{ flex: 1, overflowY: "auto", border: "1px solid var(--border)", borderRadius: "8px", padding: "1rem" }}>
                        {filteredPrototypes.length === 0 ? (
                            <div style={{ textAlign: "center", color: "var(--muted)", padding: "2rem 0" }}>
                                No verified prototypes found. User-verified attributes will appear here.
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
                                                <div style={{ fontSize: "0.75rem", color: "var(--muted)", marginBottom: "0.25rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                                                    {proto.attribute}
                                                </div>
                                                <div style={{ fontWeight: 600, fontSize: "0.95rem" }}>{proto.value}</div>
                                            </div>
                                            <span
                                                style={{
                                                    padding: "0.25rem 0.5rem",
                                                    borderRadius: "4px",
                                                    background: "var(--success-bg)",
                                                    color: "var(--success)",
                                                    fontSize: "0.75rem",
                                                    fontWeight: 600,
                                                }}
                                            >
                                                {proto.count} verified
                                            </span>
                                        </div>
                                        <div style={{ fontSize: "0.8rem", color: "var(--muted)" }}>
                                            Frames: {proto.frame_ids.slice(0, 5).map(id => `#${id}`).join(", ")}
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
