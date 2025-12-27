import { useEffect, useMemo, useState } from "react";
import { ActorDetection, Frame, Prediction, SceneAttribute } from "../lib/types";

type Props = {
    frame?: Frame;
    onSaveMetadata: (frameId: number, updates: Partial<Frame>) => void;
    onApplyOverride: (frameId: number, prediction: Prediction | string) => void;
    onSaveScene: (frameId: number, attributes: SceneAttribute[]) => void;
    onSaveActors: (frameId: number, detections: ActorDetection[]) => void;
};

type Tab = "core" | "tags" | "scene" | "actors";

export function FrameEditPanel({
    frame,
    onSaveMetadata,
    onApplyOverride,
    onSaveScene,
    onSaveActors,
}: Props) {
    const [activeTab, setActiveTab] = useState<Tab>("core");

    // -- Core Metadata State --
    const [draftMetadata, setDraftMetadata] = useState<Partial<Frame>>({});

    // -- Override/Tags State --
    const [overrideTitle, setOverrideTitle] = useState("");
    const [selectedModelPrediction, setSelectedModelPrediction] = useState<string>("");
    const [overrideNotes, setOverrideNotes] = useState("");

    // -- Scene State --
    const [sceneRows, setSceneRows] = useState<SceneAttribute[]>([]);

    // -- Actor State --
    const [actorRows, setActorRows] = useState<ActorDetection[]>([]);

    useEffect(() => {
        if (frame) {
            // Core
            setDraftMetadata({
                movieId: frame.movieId,

                predictedTimestamp: frame.predictedTimestamp ?? undefined,
                predictedShotId: frame.predictedShotId ?? undefined,
                shotTimestamp: frame.shotTimestamp ?? undefined,
                sceneSummary: frame.sceneSummary ?? undefined,
                metadataSource: frame.metadataSource ?? undefined,
                status: frame.status,
                filePath: frame.filePath,
                storageUri: frame.storageUri ?? undefined,
                matchConfidence: frame.matchConfidence ?? undefined,
                capturedAt: frame.capturedAt ?? undefined,
            });

            // Tags/Override (reset state)
            setOverrideTitle("");
            setSelectedModelPrediction("");
            setOverrideNotes("");

            // Scene
            setSceneRows(frame.sceneAttributes ?? []);

            // Actors
            setActorRows(frame.actors ?? []);
        } else {
            setDraftMetadata({});
            setSceneRows([]);
            setActorRows([]);
        }
    }, [frame]);

    const selectedPrediction = useMemo(() => {
        if (!frame) return undefined;
        return frame.predictions.find(
            (prediction) =>
                `${prediction.source}-${prediction.title}` === selectedModelPrediction,
        );
    }, [frame, selectedModelPrediction]);

    // -- Core Handlers --
    const updateMetadata = (key: keyof Frame, value: string) => {
        setDraftMetadata((prev) => ({ ...prev, [key]: value }));
    };

    // -- Scene Handlers --
    const updateSceneRow = (index: number, key: keyof SceneAttribute, value: string) => {
        setSceneRows((prev) => {
            const next = [...prev];
            const updated = { ...next[index], [key]: value };
            if (key === "confidence") {
                const parsed = Number(value);
                updated.confidence = Number.isNaN(parsed) ? undefined : parsed;
            }
            next[index] = updated;
            return next;
        });
    };
    const addSceneRow = () => setSceneRows((prev) => [...prev, { attribute: "", value: "" }]);
    const removeSceneRow = (index: number) => setSceneRows((prev) => prev.filter((_, idx) => idx !== index));

    // -- Actor Handlers --
    const updateActorRow = (index: number, key: keyof ActorDetection, value: string) => {
        setActorRows((prev) => {
            const next = [...prev];
            const updated = { ...next[index] };
            if (key === "castMemberId") {
                updated.castMemberId = value === "" ? null : Number(value);
            } else if (key === "confidence") {
                updated.confidence = value === "" ? undefined : Number(value);
            } else if (key === "faceIndex") {
                updated.faceIndex = value === "" ? undefined : Number(value);
            } else if (key === "bbox") {
                // handle simple csv input for bbox
                const parts = value.split(",").map(v => Number(v.trim())).filter(n => !isNaN(n));
                updated.bbox = parts.length > 0 ? parts : null;
            } else if (key === "clusterLabel" || key === "trackStatus" || key === "emotion") {
                updated[key] = value === "" ? undefined : value;
            } else if (key === "poseYaw") {
                updated.poseYaw = value === "" ? undefined : Number(value);
            } else if (key === "posePitch") {
                updated.posePitch = value === "" ? undefined : Number(value);
            } else if (key === "poseRoll") {
                updated.poseRoll = value === "" ? undefined : Number(value);
            }
            next[index] = updated;
            return next;
        });
    };
    const addActorRow = () => setActorRows((prev) => [...prev, {
        castMemberId: null,
        confidence: undefined,
        faceIndex: undefined,
        clusterLabel: undefined,
        trackStatus: undefined,
        emotion: undefined,
        poseYaw: undefined,
        posePitch: undefined,
        poseRoll: undefined,
    }]);
    const removeActorRow = (index: number) => setActorRows((prev) => prev.filter((_, idx) => idx !== index));


    if (!frame) return null;

    return (
        <div className="sidebar__section" style={{ minHeight: 400 }}>
            <div style={{ display: "flex", borderBottom: "1px solid var(--border)", marginBottom: "1rem" }}>
                {(["core", "tags", "scene", "actors"] as Tab[]).map((tab) => (
                    <button
                        key={tab}
                        className={`button ${activeTab === tab ? "button--primary" : "button--ghost"}`}
                        style={{
                            flex: 1,
                            borderRadius: 0,
                            borderBottom: activeTab === tab ? "2px solid var(--foreground)" : "none",
                            opacity: activeTab === tab ? 1 : 0.6,
                            padding: "0.5rem 0"
                        }}
                        onClick={() => setActiveTab(tab)}
                    >
                        {tab.charAt(0).toUpperCase() + tab.slice(1)}
                    </button>
                ))}
            </div>

            {activeTab === "core" && (
                <div className="animate-fade-in">
                    <label className="label" htmlFor="movieId">Movie ID</label>
                    <input
                        id="movieId"
                        className="input"
                        value={draftMetadata.movieId ?? ""}
                        onChange={(event) => setDraftMetadata((prev) => ({ ...prev, movieId: event.target.value ? Number(event.target.value) : null }))}
                        placeholder="123"
                    />



                    <label className="label" htmlFor="status" style={{ marginTop: 8 }}>Status</label>
                    <select
                        id="status"
                        className="select"
                        value={draftMetadata.status}
                        onChange={(event) => updateMetadata("status", event.target.value)}
                    >
                        <option value="needs_analyzing">Needs Analyzing</option>
                        <option value="analyzed">Analyzed</option>
                        <option value="tmdb_only">Tmdb Only</option>
                        <option value="confirmed">Confirmed</option>
                    </select>

                    <label className="label" htmlFor="filePath" style={{ marginTop: 8 }}>File path</label>
                    <input
                        id="filePath"
                        className="input"
                        value={draftMetadata.filePath ?? ""}
                        onChange={(event) => updateMetadata("filePath", event.target.value)}
                        placeholder="frames/clip/image.jpg"
                    />

                    <label className="label" htmlFor="sceneSummary" style={{ marginTop: 8 }}>Scene summary</label>
                    <textarea
                        id="sceneSummary"
                        className="input"
                        style={{ minHeight: 80 }}
                        value={draftMetadata.sceneSummary ?? ""}
                        onChange={(event) => updateMetadata("sceneSummary", event.target.value)}
                        placeholder="Short description of the shot."
                    />

                    <button
                        className="button button--primary"
                        style={{ marginTop: "1rem", width: "100%" }}
                        onClick={() => onSaveMetadata(frame.id, draftMetadata)}
                    >
                        Save Core Metadata
                    </button>
                </div>
            )}

            {activeTab === "tags" && (
                <div className="animate-fade-in">
                    <label className="label" htmlFor="predictionSelect">
                        Choose a model prediction
                    </label>
                    <select
                        id="predictionSelect"
                        className="select"
                        value={selectedModelPrediction}
                        onChange={(event) => setSelectedModelPrediction(event.target.value)}
                    >
                        <option value="">Select prediction...</option>
                        {frame.predictions.map((prediction) => (
                            <option key={`${prediction.source}-${prediction.title}`} value={`${prediction.source}-${prediction.title}`}>
                                {prediction.title} ({(prediction.confidence * 100).toFixed(1)}% · {prediction.source})
                            </option>
                        ))}
                    </select>

                    <div style={{ margin: "1rem 0 0.5rem" }}>
                        <span className="label">Or enter manually</span>
                        <input
                            className="input"
                            placeholder="Tag / Movie title"
                            value={overrideTitle}
                            onChange={(event) => setOverrideTitle(event.target.value)}
                        />
                    </div>

                    <label className="label" htmlFor="notes" style={{ marginTop: "0.75rem" }}>
                        Notes (optional)
                    </label>
                    <textarea
                        id="notes"
                        className="input"
                        style={{ minHeight: 90, resize: "vertical" }}
                        value={overrideNotes}
                        onChange={(event) => setOverrideNotes(event.target.value)}
                        placeholder="Reason for tag..."
                    />

                    <button
                        className="button button--primary"
                        style={{ marginTop: "1rem", width: "100%" }}
                        onClick={() => {
                            if (selectedPrediction) {
                                onApplyOverride(frame.id, selectedPrediction);
                                setSelectedModelPrediction("");
                            } else if (overrideTitle.trim()) {
                                onApplyOverride(frame.id, overrideTitle.trim());
                                setOverrideTitle("");
                            }
                            setOverrideNotes("");
                        }}
                    >
                        Apply Tag
                    </button>
                </div>
            )}

            {activeTab === "scene" && (
                <div className="animate-fade-in">
                    {sceneRows.map((row, index) => (
                        <div key={index} style={{ marginBottom: "1rem", paddingBottom: "1rem", borderBottom: '1px solid var(--border)' }}>
                            <div style={{ marginBottom: 8 }}>
                                <label className="label">Attribute</label>
                                <input
                                    className="input"
                                    value={row.attribute}
                                    onChange={(event) => updateSceneRow(index, "attribute", event.target.value)}
                                    placeholder="e.g. time_of_day"
                                    style={{ width: "100%" }}
                                />
                            </div>
                            <div style={{ marginBottom: 8 }}>
                                <label className="label">Value</label>
                                <input
                                    className="input"
                                    value={row.value}
                                    onChange={(event) => updateSceneRow(index, "value", event.target.value)}
                                    placeholder="e.g. night"
                                    style={{ width: "100%" }}
                                />
                            </div>
                            <div style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
                                <div style={{ flex: 1 }}>
                                    <label className="label">Confidence</label>
                                    <input
                                        className="input"
                                        value={row.confidence ?? ""}
                                        onChange={(event) => updateSceneRow(index, "confidence", event.target.value)}
                                        placeholder="0.92"
                                        style={{ width: "100%" }}
                                    />
                                </div>
                                <button
                                    className="button button--ghost"
                                    style={{ color: 'var(--danger)', height: 38 }}
                                    type="button"
                                    onClick={() => removeSceneRow(index)}
                                >
                                    Remove
                                </button>
                            </div>
                        </div>
                    ))}

                    <div style={{ display: "flex", gap: 8, marginTop: '1rem' }}>
                        <button className="button" type="button" onClick={addSceneRow}>
                            + Add Attribute
                        </button>
                        <button className="button button--primary" style={{ flex: 1 }} type="button" onClick={() => onSaveScene(frame.id, sceneRows.filter(r => r.attribute && r.value))}>
                            Save Scene
                        </button>
                    </div>
                </div>
            )}

            {activeTab === "actors" && (
                <div className="animate-fade-in">
                    {actorRows.map((row, index) => (
                        <div key={index} style={{ marginBottom: "1rem", paddingBottom: "1rem", borderBottom: '1px solid var(--border)' }}>
                            <div style={{ marginBottom: 8 }}>
                                <label className="label">Cast Member ID</label>
                                <input
                                    className="input"
                                    value={row.castMemberId ?? ""}
                                    onChange={(event) => updateActorRow(index, "castMemberId", event.target.value)}
                                    placeholder="Database ID"
                                    style={{ width: "100%" }}
                                />
                            </div>

                            <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
                                <div style={{ flex: 1 }}>
                                    <label className="label">Face Index</label>
                                    <input
                                        className="input"
                                        value={row.faceIndex ?? ""}
                                        onChange={(event) => updateActorRow(index, "faceIndex", event.target.value)}
                                        placeholder="0"
                                        style={{ width: "100%" }}
                                    />
                                </div>
                                <div style={{ flex: 1 }}>
                                    <label className="label">Confidence</label>
                                    <input
                                        className="input"
                                        value={row.confidence ?? ""}
                                        onChange={(event) => updateActorRow(index, "confidence", event.target.value)}
                                        placeholder="0.0 - 1.0"
                                        style={{ width: "100%" }}
                                    />
                                </div>
                            </div>

                            <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
                                <div style={{ flex: 1 }}>
                                    <label className="label">Emotion</label>
                                    <input
                                        className="input"
                                        placeholder="happy"
                                        value={row.emotion ?? ""}
                                        onChange={(e) => updateActorRow(index, "emotion", e.target.value)}
                                        style={{ width: "100%" }}
                                    />
                                </div>
                                <div style={{ flex: 1 }}>
                                    <label className="label">Pose (Y,P,R)</label>
                                    <input
                                        className="input"
                                        placeholder="0,0,0"
                                        value={[row.poseYaw, row.posePitch, row.poseRoll].filter(x => x !== undefined).join(",")}
                                        onChange={(e) => {
                                            const [y, p, r] = e.target.value.split(",");
                                            updateActorRow(index, "poseYaw", y);
                                            updateActorRow(index, "posePitch", p);
                                            updateActorRow(index, "poseRoll", r);
                                        }}
                                        style={{ width: "100%" }}
                                    />
                                </div>
                            </div>

                            <button
                                className="button button--ghost"
                                style={{ color: 'var(--danger)', width: "100%" }}
                                type="button"
                                onClick={() => removeActorRow(index)}
                            >
                                Remove Entry
                            </button>
                        </div>
                    ))}

                    <div style={{ display: "flex", gap: 8, marginTop: '1rem' }}>
                        <button className="button" type="button" onClick={addActorRow}>
                            + Add Actor
                        </button>
                        <button className="button button--primary" style={{ flex: 1 }} type="button" onClick={() => onSaveActors(frame.id, actorRows.filter(r => r.castMemberId !== null || r.confidence !== undefined))}>
                            Save Actors
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
