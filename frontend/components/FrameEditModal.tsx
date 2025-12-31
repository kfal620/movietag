import { useEffect, useMemo, useState } from "react";
import Image from "next/image";
import { ActorDetection, Frame, Prediction, SceneAttribute, TmdbSearchResult } from "../lib/types";
import { AnalysisLogModal } from "./AnalysisLogModal";
import { VisionPipelineSelector } from "./VisionPipelineSelector";
import { getSelectedPipelineId, setSelectedPipelineId } from "../lib/visionSettings";

type Props = {
  frame?: Frame;
  isOpen: boolean;
  onClose: () => void;
  onSaveMetadata: (frameId: number, updates: Partial<Frame>) => void;
  onApplyOverride: (frameId: number, prediction: Prediction | string) => void;
  onSaveScene: (frameId: number, attributes: SceneAttribute[]) => void;
  onSaveActors: (frameId: number, detections: ActorDetection[]) => void;
  onAssignTmdb?: (frameId: number, tmdbId: number) => Promise<void>;
  onRunAnalysis?: (frameId: number) => Promise<string>;
  authToken?: string;
};

type Tab = "movie" | "scene" | "actors";

export function FrameEditModal({
  frame,
  isOpen,
  onClose,
  onSaveMetadata,
  onApplyOverride,
  onSaveScene,
  onSaveActors,
  onAssignTmdb,
  onRunAnalysis,
  authToken,
}: Props) {
  const [localFrame, setLocalFrame] = useState<Frame | undefined>(frame);
  const [activeTab, setActiveTab] = useState<Tab>("movie");

  useEffect(() => {
    setLocalFrame(frame);
  }, [frame]);

  // -- Core Metadata State --
  const [draftMetadata, setDraftMetadata] = useState<Partial<Frame>>({});
  const [analyzing, setAnalyzing] = useState(false);
  const [selectedPipeline, setSelectedPipeline] = useState<string>(getSelectedPipelineId());
  const [coreMessage, setCoreMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [showLog, setShowLog] = useState(false);



  // -- Scene State --
  const [sceneRows, setSceneRows] = useState<SceneAttribute[]>([]);
  const [attributeOptions, setAttributeOptions] = useState<Record<string, string[]>>({});

  // -- Actor State --
  const [actorRows, setActorRows] = useState<ActorDetection[]>([]);

  // -- TMDB State --
  const [searchQuery, setSearchQuery] = useState("");
  const [searchYear, setSearchYear] = useState("");
  const [searchResults, setSearchResults] = useState<TmdbSearchResult[]>([]);
  const [selectedTmdbId, setSelectedTmdbId] = useState<number | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [searching, setSearching] = useState(false);
  const [assigning, setAssigning] = useState(false);
  const [assignMessage, setAssignMessage] = useState<string | null>(null);

  const [freshImageUrl, setFreshImageUrl] = useState<string | null>(null);

  useEffect(() => {
    if (frame && isOpen) {
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
        capturedAt: frame.capturedAt ?? undefined,
      });
      setCoreMessage(null);



      // Scene
      setSceneRows(frame.sceneAttributes ?? []);

      // Actors
      setActorRows(frame.actors ?? []);

      // TMDB (reset state)
      setSearchQuery("");
      setSearchYear("");
      setSearchResults([]);
      setSelectedTmdbId(null);
      setSearchError(null);
      setAssignMessage(null);

      // Refresh image URL if expired
      setFreshImageUrl(null);
      const fetchFreshFrame = async () => {
        try {
          const headers: HeadersInit = {};
          if (authToken) {
            headers["Authorization"] = `Bearer ${authToken}`;
          }
          const response = await fetch(`/api/frames/${frame.id}`, { headers });
          if (response.ok) {
            const data = await response.json();
            if (data.signed_url) {
              setFreshImageUrl(data.signed_url);
            }
          }
        } catch (err) {
          console.error("Failed to refresh frame URL", err);
        }
      };
      fetchFreshFrame();

      // Fetch attribute options
      const fetchAttributeOptions = async () => {
        try {
          const response = await fetch('/api/vision/attribute-options');
          if (response.ok) {
            const data = await response.json();
            setAttributeOptions(data);
          }
        } catch (err) {
          console.error('Failed to fetch attribute options', err);
        }
      };
      fetchAttributeOptions();
    }
  }, [frame, isOpen, authToken]);



  // -- Core Handlers --
  const updateMetadata = (key: keyof Frame, value: string) => {
    setDraftMetadata((prev) => ({ ...prev, [key]: value }));
  };

  const runVisionAnalysis = async () => {
    if (!localFrame) return;
    if (!authToken) {
      setCoreMessage({ type: "error", text: "Authentication required for analysis." });
      return;
    }

    setAnalyzing(true);
    setCoreMessage(null);

    try {
      // Use the new pipeline-aware analysis endpoint
      const response = await fetch("/api/vision/analyze", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${authToken}`,
        },
        body: JSON.stringify({
          frame_id: localFrame.id,
          pipeline_id: selectedPipeline,
          force: true,  // Always run fresh analysis
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || "Analysis failed");
      }

      const result = await response.json();

      // Show success message with timing info
      setCoreMessage({
        type: "success",
        text: result.cached
          ? `Analysis complete (cached, ${result.embedding_dimension}-dim)`
          : `Analysis complete (${result.embed_time?.toFixed(2)}s embed, ${result.attribute_time?.toFixed(2)}s attr)`
      });

      // Refresh the frame to get all updated data (including analysis_log)
      const frameRes = await fetch(`/api/frames/${localFrame.id}`, {
        headers: authToken ? { Authorization: `Bearer ${authToken}` } : undefined,
      });

      if (frameRes.ok) {
        const newFrameData = await frameRes.json();

        // Update local frame with all new data
        const updatedFrame = {
          ...newFrameData,
          predictions: localFrame?.predictions || []
        };
        setLocalFrame(updatedFrame);

        // Update scene attributes in the Scene tab
        setSceneRows(updatedFrame.sceneAttributes || updatedFrame.scene_attributes || []);

        // Update the status in draftMetadata to reflect the backend change
        setDraftMetadata((prev) => ({ ...prev, status: updatedFrame.status }));

        // The analysis_log should now be available for the "View Log" button
        // which checks for localFrame.analysisLog
      }

    } catch (error) {
      setCoreMessage({
        type: "error",
        text: error instanceof Error ? error.message : "Analysis failed"
      });
    } finally {
      setAnalyzing(false);
    }
  };

  const handlePipelineChange = (pipelineId: string) => {
    setSelectedPipeline(pipelineId);
    setSelectedPipelineId(pipelineId); // Save to localStorage
  };

  // -- Scene Handlers --
  const updateSceneRow = (index: number, key: keyof SceneAttribute, value: string) => {
    setSceneRows((prev) => {
      const next = [...prev];
      const updated = { ...next[index], [key]: value, isVerified: true };
      if (key === "confidence") {
        const parsed = Number(value);
        updated.confidence = Number.isNaN(parsed) ? undefined : parsed;
      }
      next[index] = updated;
      return next;
    });
  };
  const addSceneRow = () => setSceneRows((prev) => [...prev, { attribute: "", value: "", isVerified: true }]);
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

  // -- TMDB Handlers --
  const runSearch = async () => {
    if (!searchQuery.trim()) {
      setSearchError("Enter a movie title to search TMDb.");
      return;
    }
    if (!authToken) {
      setSearchError("Set a moderator or admin token to search TMDb.");
      return;
    }
    setSearching(true);
    setSearchError(null);
    try {
      const params = new URLSearchParams({ q: searchQuery.trim() });
      if (searchYear.trim()) params.set("year", searchYear.trim());
      const response = await fetch(`/api/movies/search?${params.toString()}`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || "TMDb search failed");
      }
      const payload = await response.json();
      setSearchResults(payload.items ?? []);
      setAssignMessage(null);
    } catch (error) {
      const message = error instanceof Error ? error.message : "TMDb search failed";
      setSearchError(message);
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  };

  const confirmAssignment = async () => {
    if (!selectedTmdbId) {
      setAssignMessage("Choose a movie result before confirming.");
      return;
    }
    if (!onAssignTmdb || !localFrame) return;
    setAssigning(true);
    setAssignMessage(null);
    try {
      await onAssignTmdb(localFrame.id, selectedTmdbId);
      setAssignMessage("Frame assigned to the selected movie.");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Assignment failed";
      setAssignMessage(message);
    } finally {
      setAssigning(false);
    }
  };

  const handleSave = async () => {
    if (!localFrame) return;

    // Collect all save operations as promises
    const savePromises = [
      onSaveMetadata(localFrame.id, draftMetadata),
      onSaveScene(localFrame.id, sceneRows.filter(r => r.attribute && r.value)),
      onSaveActors(localFrame.id, actorRows.filter(r => r.castMemberId !== null || r.confidence !== undefined)),
    ];

    // Wait for all saves to complete before closing
    await Promise.all(savePromises);

    onClose();
  };

  if (!isOpen || !localFrame) return null;

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: "rgba(0, 0, 0, 0.8)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
        padding: "2rem",
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: "var(--panel)",
          border: "1px solid var(--border)",
          borderRadius: "16px",
          maxWidth: "1200px",
          width: "100%",
          maxHeight: "90vh",
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header with image and title */}
        <div style={{ display: "flex", padding: "1.5rem", borderBottom: "1px solid var(--border)" }}>
          <div style={{ flex: 1, marginRight: "1.5rem" }}>
            <div style={{ position: "relative", width: "100%", height: "300px", borderRadius: "12px", overflow: "hidden" }}>
              <Image src={freshImageUrl || localFrame.imageUrl} alt={localFrame.movieTitle} fill style={{ objectFit: "cover" }} />
            </div>
          </div>
          <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
            <h2 style={{ margin: 0, marginBottom: "0.5rem" }}>{localFrame.movieTitle}</h2>
            <p style={{ color: "var(--muted)", margin: 0, marginBottom: "0.5rem" }}>
              Status: {localFrame.status.replace("_", " ")}
            </p>

            {/* Show which pipeline generated the current attributes */}
            {localFrame.analysisLog && localFrame.analysisLog._metadata && (
              <div style={{
                fontSize: "0.85rem",
                color: "var(--muted)",
                marginBottom: "1rem",
                padding: "0.5rem",
                background: "var(--surface)",
                borderRadius: "6px",
                border: "1px solid var(--border)"
              }}>
                <strong>Current Analysis:</strong> {localFrame.analysisLog._metadata.pipeline_name || "Unknown"}
                {" "}
                <span style={{ opacity: 0.7 }}>
                  ({localFrame.analysisLog._metadata.embedding_dimension || "?"}-dim,
                  {" "}{localFrame.analysisLog._metadata.device || "unknown"})
                </span>
              </div>
            )}

            {/* Pipeline Selector */}
            <div style={{ marginBottom: "0.5rem" }}>
              <label style={{ fontSize: "0.85rem", color: "var(--muted)", marginBottom: "0.25rem", display: "block" }}>
                Run New Analysis With:
              </label>
              <VisionPipelineSelector
                value={selectedPipeline}
                onChange={handlePipelineChange}
                authToken={authToken}
              />
            </div>

            <div style={{ display: "flex", gap: "0.5rem", marginTop: "auto" }}>
              <button
                type="button"
                className="button button--ghost"
                onClick={runVisionAnalysis}
                disabled={analyzing || !authToken}
                style={{ fontSize: "0.9rem", padding: "0.5rem 0.75rem" }}
              >
                {analyzing ? "Analyzing..." : "Run Vision Analysis"}
              </button>
              {localFrame.analysisLog && (
                <button
                  type="button"
                  className="button button--ghost"
                  onClick={() => setShowLog(true)}
                  style={{ fontSize: "0.9rem", padding: "0.5rem 0.75rem" }}
                >
                  View Log
                </button>
              )}
            </div>
            {coreMessage && (
              <p style={{ marginTop: "0.25rem", fontSize: "0.85rem", color: coreMessage.type === "success" ? "var(--success)" : "var(--danger)" }}>
                {coreMessage.text}
              </p>
            )}
          </div>
        </div>

        {/* Tab Navigation */}
        <div style={{ display: "flex", borderBottom: "1px solid var(--border)", marginBottom: "1rem" }}>
          {(["core", "tags", "scene", "actors", "tmdb"] as Tab[]).map((tab) => (
            <button
              key={tab}
              className={`button ${activeTab === tab ? "button--primary" : "button--ghost"}`}
              style={{
                flex: 1,
                borderRadius: 0,
                borderBottom: activeTab === tab ? "2px solid var(--foreground)" : "none",
                opacity: activeTab === tab ? 1 : 0.6,
                padding: "0.75rem 0"
              }}
              onClick={() => setActiveTab(tab)}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div style={{ flex: 1, overflowY: "auto", padding: "0 1.5rem 1.5rem" }}>
          {activeTab === "movie" && (
            <div className="animate-fade-in">
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                <div>
                  <label className="label" htmlFor="movieId">Movie ID</label>
                  <input
                    id="movieId"
                    className="input"
                    value={draftMetadata.movieId ?? ""}
                    onChange={(event) => setDraftMetadata((prev) => ({ ...prev, movieId: event.target.value ? Number(event.target.value) : null }))}
                    placeholder="123"
                  />
                </div>

                <div>
                  <label className="label" htmlFor="status">Status</label>
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
                </div>
              </div>

              <label className="label" htmlFor="filePath" style={{ marginTop: "1rem" }}>File path</label>
              <input
                id="filePath"
                className="input"
                value={draftMetadata.filePath ?? ""}
                readOnly
                disabled
                placeholder="frames/clip/image.jpg"
              />

              <label className="label" htmlFor="sceneSummary" style={{ marginTop: "1rem" }}>Movie Description</label>
              <textarea
                id="sceneSummary"
                className="input"
                style={{ minHeight: 60 }}
                value={draftMetadata.sceneSummary ?? ""}
                onChange={(event) => updateMetadata("sceneSummary", event.target.value)}
                placeholder="Short description of the shot."
              />

              {/* TMDB Search Integration */}
              <div style={{ marginTop: "2rem", paddingTop: "1.5rem", borderTop: "1px solid var(--border)" }}>
                <h3 style={{ marginTop: 0, marginBottom: "0.5rem", fontSize: "1rem" }}>Search & Assign Movie</h3>
                <p className="muted" style={{ marginBottom: "1rem", fontSize: "0.9rem" }}>
                  Enter a title (and optional year) to override the frame&apos;s movie. Results require a moderator or admin token.
                </p>
                <label className="label" htmlFor="tmdbQuery">
                  Movie title
                </label>
                <input
                  id="tmdbQuery"
                  className="input"
                  placeholder="e.g. The Matrix"
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                />
                <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                  <input
                    className="input"
                    placeholder="Year (optional)"
                    value={searchYear}
                    onChange={(event) => setSearchYear(event.target.value)}
                    style={{ flex: 1 }}
                  />
                  <button className="button button--primary" type="button" onClick={runSearch} disabled={searching}>
                    {searching ? "Searching..." : "Search TMDb"}
                  </button>
                </div>
                {searchError ? <p style={{ color: "var(--danger)", marginTop: 8 }}>{searchError}</p> : null}
                {searchResults.length ? (
                  <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 8, maxHeight: "300px", overflowY: "auto" }}>
                    {searchResults.map((result) => {
                      const isSelected = selectedTmdbId === result.tmdb_id;
                      const posterUrl =
                        result.poster_path && result.poster_path.startsWith("http")
                          ? result.poster_path
                          : result.poster_path
                            ? `https://image.tmdb.org/t/p/w200${result.poster_path}`
                            : "/placeholder-thumbnail.svg";
                      return (
                        <div
                          key={result.tmdb_id}
                          style={{
                            display: "flex",
                            gap: 12,
                            border: isSelected ? "2px solid var(--primary)" : "1px solid var(--border)",
                            background: isSelected ? "rgba(59, 130, 246, 0.08)" : undefined,
                            cursor: "pointer",
                            padding: 8,
                            borderRadius: 8,
                          }}
                          onClick={() => setSelectedTmdbId(result.tmdb_id)}
                        >
                          <div style={{ position: "relative", width: 60, height: 90, flexShrink: 0 }}>
                            <Image src={posterUrl} alt={result.title} fill style={{ objectFit: "cover", borderRadius: 6 }} sizes="60px" />
                          </div>
                          <div style={{ flex: 1 }}>
                            <div style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 4 }}>
                              <strong>{result.title}</strong>
                              <span className="chip chip--muted">{result.release_year ?? "Unknown year"}</span>
                            </div>
                            <p style={{ margin: 0, lineHeight: 1.4, fontSize: "0.9rem", color: "var(--muted)" }}>
                              {result.overview || "No synopsis available."}
                            </p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  searchQuery &&
                  !searching &&
                  !searchError && <p className="muted" style={{ marginTop: 12 }}>No results yet. Try another title or year.</p>
                )}
                <button
                  className="button"
                  type="button"
                  style={{ marginTop: 12, width: "100%" }}
                  disabled={!selectedTmdbId || assigning}
                  onClick={confirmAssignment}
                >
                  {assigning ? "Assigning..." : "Confirm assignment"}
                </button>
                {assignMessage ? <p style={{ marginTop: 8, color: assignMessage.toLowerCase().includes("assign") ? "var(--success)" : "var(--danger)" }}>{assignMessage}</p> : null}
              </div>
            </div>
          )}



          {activeTab === "scene" && (
            <div className="animate-fade-in">
              {localFrame.analysisLog && localFrame.analysisLog._metadata && (
                <div style={{
                  fontSize: "0.85rem",
                  color: "var(--muted)",
                  marginBottom: "1rem",
                  padding: "0.75rem",
                  background: "var(--surface)",
                  borderRadius: "6px",
                  border: "1px solid var(--border)"
                }}>
                  <strong>Attributes generated by:</strong> {localFrame.analysisLog._metadata.pipeline_name}
                  <br />
                  <span style={{ opacity: 0.7 }}>
                    Embedding: {localFrame.analysisLog._metadata.embedding_dimension}-dimensional,
                    Device: {localFrame.analysisLog._metadata.device}
                  </span>
                </div>
              )}

              {/* Column Labels */}
              <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.5rem", paddingLeft: "0.25rem" }}>
                <div style={{ flex: 1 }}>
                  <label className="label" style={{ marginBottom: 0, fontSize: "0.85rem", color: "var(--muted)" }}>
                    Attribute
                  </label>
                </div>
                <div style={{ flex: 1 }}>
                  <label className="label" style={{ marginBottom: 0, fontSize: "0.85rem", color: "var(--muted)" }}>
                    Value
                  </label>
                </div>
                <div style={{ flex: 0.5 }}>
                  <label className="label" style={{ marginBottom: 0, fontSize: "0.85rem", color: "var(--muted)" }}>
                    Confidence Score
                  </label>
                </div>
                <div style={{ width: "44px" }}>{/* Spacer for delete button */}</div>
              </div>

              {sceneRows.map((row, index) => (
                <div key={index} style={{ display: "flex", gap: "0.5rem", alignItems: "flex-end", marginBottom: "0.5rem" }}>
                  <div style={{ flex: 1, position: "relative" }}>
                    <input
                      className="input"
                      value={row.attribute}
                      onChange={(event) => updateSceneRow(index, "attribute", event.target.value)}
                      placeholder="Attribute"
                      style={{ fontSize: "0.9rem", paddingLeft: row.isVerified ? "2rem" : undefined }}
                    />
                    {row.isVerified && (
                      <span
                        title="Verified by user"
                        style={{
                          position: "absolute",
                          left: "0.5rem",
                          top: "50%",
                          transform: "translateY(-50%)",
                          color: "var(--success)",
                          cursor: "help"
                        }}
                      >
                        ✓
                      </span>
                    )}
                  </div>
                  <div style={{ flex: 1 }}>
                    <select
                      className="select"
                      value={row.value}
                      onChange={(event) => updateSceneRow(index, "value", event.target.value)}
                      style={{ fontSize: "0.9rem" }}
                      disabled={!row.attribute || !attributeOptions[row.attribute]}
                    >
                      <option value="">Select value...</option>
                      {row.attribute && attributeOptions[row.attribute]?.map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div style={{ flex: 0.5 }}>
                    <input
                      className="input"
                      value={row.confidence ?? ""}
                      onChange={(event) => updateSceneRow(index, "confidence", event.target.value)}
                      placeholder="Conf."
                      style={{ fontSize: "0.9rem" }}
                    />
                  </div>
                  <button
                    className="button button--ghost"
                    style={{ color: 'var(--danger)', padding: '0.25rem 0.5rem', fontSize: '0.8rem' }}
                    type="button"
                    onClick={() => removeSceneRow(index)}
                  >
                    ×
                  </button>
                </div>
              ))}

              <button className="button" type="button" onClick={addSceneRow} style={{ marginTop: "0.5rem" }}>
                + Add Attribute
              </button>
            </div>
          )}

          {activeTab === "actors" && (
            <div className="animate-fade-in">
              {actorRows.map((row, index) => (
                <div key={index} style={{ marginBottom: "0.75rem", padding: "0.75rem", border: '1px solid var(--border)', borderRadius: 8 }}>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: "0.5rem", marginBottom: "0.5rem" }}>
                    <div>
                      <input
                        className="input"
                        value={row.castMemberId ?? ""}
                        onChange={(event) => updateActorRow(index, "castMemberId", event.target.value)}
                        placeholder="Cast ID"
                        style={{ fontSize: "0.9rem" }}
                      />
                    </div>
                    <div>
                      <input
                        className="input"
                        value={row.faceIndex ?? ""}
                        onChange={(event) => updateActorRow(index, "faceIndex", event.target.value)}
                        placeholder="Face #"
                        style={{ fontSize: "0.9rem" }}
                      />
                    </div>
                    <div>
                      <input
                        className="input"
                        value={row.confidence ?? ""}
                        onChange={(event) => updateActorRow(index, "confidence", event.target.value)}
                        placeholder="Conf."
                        style={{ fontSize: "0.9rem" }}
                      />
                    </div>
                    <div>
                      <input
                        className="input"
                        placeholder="Emotion"
                        value={row.emotion ?? ""}
                        onChange={(e) => updateActorRow(index, "emotion", e.target.value)}
                        style={{ fontSize: "0.9rem" }}
                      />
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                    <input
                      className="input"
                      placeholder="Pose (Y,P,R)"
                      value={[row.poseYaw, row.posePitch, row.poseRoll].filter(x => x !== undefined).join(",")}
                      onChange={(e) => {
                        const [y, p, r] = e.target.value.split(",");
                        updateActorRow(index, "poseYaw", y);
                        updateActorRow(index, "posePitch", p);
                        updateActorRow(index, "poseRoll", r);
                      }}
                      style={{ flex: 1, fontSize: "0.9rem" }}
                    />
                    <button
                      className="button button--ghost"
                      style={{ color: 'var(--danger)', padding: '0.25rem 0.5rem', fontSize: '0.8rem' }}
                      type="button"
                      onClick={() => removeActorRow(index)}
                    >
                      ×
                    </button>
                  </div>
                </div>
              ))}

              <button className="button" type="button" onClick={addActorRow} style={{ marginTop: "0.5rem" }}>
                + Add Actor
              </button>
            </div>
          )}

        </div>

        {/* Footer with action buttons */}
        <div style={{ display: "flex", gap: "1rem", padding: "1.5rem", borderTop: "1px solid var(--border)" }}>
          <button className="button button--ghost" style={{ flex: 1 }} onClick={onClose}>
            Cancel
          </button>
          <button className="button button--primary" style={{ flex: 1 }} onClick={handleSave}>
            Save Changes
          </button>
        </div>
      </div>
      {showLog && localFrame && <AnalysisLogModal frame={localFrame} onClose={() => setShowLog(false)} />}
    </div >
  );
}