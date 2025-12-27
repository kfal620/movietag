/* eslint-disable @next/next/no-img-element */
"use client";

import { useEffect, useMemo, useState } from "react";
import useSWR from "swr";
import { ActorDetection, Frame, Prediction, SceneAttribute } from "../lib/types";
import { FrameSidebar } from "../components/FrameSidebar";
import { FrameGrid } from "../components/FrameGrid";
import { Toolbar } from "../components/Toolbar";
import { ExportPanel } from "../components/ExportPanel";
import { SettingsPanel } from "../components/SettingsPanel";
import { StorageExplorer } from "../components/StorageExplorer";
import { Sidebar } from "../components/Sidebar";
import { VisionModelsPanel } from "../components/VisionModelsPanel";
import { FrameEditModal } from "../components/FrameEditModal";


const statusFilters: { label: string; value: Frame["status"] | "all" }[] = [
  { label: "All", value: "all" },
  { label: "New", value: "new" },
  { label: "Needs review", value: "needs_review" },
  { label: "Confirmed", value: "confirmed" },
  { label: "Overridden", value: "overridden" },
  { label: "Tagged", value: "tagged" },
];

type FrameApiItem = {
  id: number;
  movie_id: number | null;
  movie_title?: string | null;
  status: Frame["status"];
  signed_url?: string | null;
  file_path: string;
  predicted_timestamp?: string | null;
  predicted_shot_id?: string | null;
  shot_timestamp?: string | null;
  scene_summary?: string | null;
  metadata_source?: string | null;
  match_confidence?: number | null;
  storage_uri?: string | null;
  captured_at?: string | null;
  embedding_model?: string | null;
  embedding_model_version?: string | null;
  tags?: { id: number; name: string; confidence?: number }[];
  scene_attributes?: { id: number; attribute: string; value: string; confidence?: number }[];
  actor_detections?: {
    id: number;
    cast_member_id: number | null;
    cast_member_name?: string | null;
    confidence?: number;
    face_index?: number | null;
    bbox?: number[] | null;
    cluster_label?: string | null;
    track_status?: string | null;
    emotion?: string | null;
    pose?: { yaw?: number | null; pitch?: number | null; roll?: number | null };
  }[];
};

type FramesApiResponse = { items: FrameApiItem[]; total: number };

const authedFetcher = async (url: string, token?: string) => {
  const response = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed (${response.status})`);
  }
  return response.json();
};

const deriveImageUrl = (item: FrameApiItem): string => {
  const candidates = [item.signed_url, item.file_path, item.storage_uri];
  const resolved = candidates.find(
    (value) => value?.startsWith("http://") || value?.startsWith("https://"),
  );

  return resolved ?? "/placeholder-thumbnail.svg";
};

export default function Home() {
  const [movieFilter, setMovieFilter] = useState("");
  const [tagFilter, setTagFilter] = useState("");
  const [actorFilter, setActorFilter] = useState("");
  const [timeOfDayFilter, setTimeOfDayFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<Frame["status"] | "all">("all");
  const [authToken, setAuthToken] = useState<string>("");
  const [settingsStatus, setSettingsStatus] = useState<string | null>(null);
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const [storageMessage, setStorageMessage] = useState<string | null>(null);
  const [selectedView, setSelectedView] = useState("frames");
  const [analysisScope, setAnalysisScope] = useState<"selected" | "filtered">("selected");
  const [analysisJob, setAnalysisJob] = useState<{
    id: string;
    status: string;
    processed?: number | null;
    total?: number | null;
    error?: string | null;
  } | null>(null);
  const [analysisMessage, setAnalysisMessage] = useState<string | null>(null);
  const [editModalFrameId, setEditModalFrameId] = useState<number | null>(null);

  const framesUrl = useMemo(() => {
    const params = new URLSearchParams();
    if (movieFilter) params.set("movie_id", movieFilter);
    if (statusFilter !== "all") params.set("status", statusFilter);
    if (actorFilter) params.set("cast_member_id", actorFilter);
    if (timeOfDayFilter) params.set("time_of_day", timeOfDayFilter);
    tagFilter
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean)
      .forEach((tag) => params.append("tag", tag));
    const search = params.toString();
    return `/api/frames${search ? `?${search}` : ""}`;
  }, [actorFilter, movieFilter, statusFilter, tagFilter, timeOfDayFilter]);

  useEffect(() => {
    const storedToken = window.localStorage.getItem("movietagToken");
    if (storedToken) {
      setAuthToken(storedToken);
    }
  }, []);

  const { data, mutate } = useSWR<FramesApiResponse>(
    [framesUrl, authToken],
    ([url, token]: [string, string]) => authedFetcher(url, token),
    {
      revalidateOnFocus: false,
    },
  );

  const frames: Frame[] = useMemo(
    () =>
      data?.items.map((item) => {
        const predictions: Prediction[] = [];

        return {
          id: item.id,
          movieId: item.movie_id,
          movieTitle:
            item.movie_title || (item.movie_id ? `Movie #${item.movie_id}` : "Unknown movie"),
          filePath: item.file_path,
          storageUri: item.storage_uri,
          signedUrl: item.signed_url ?? undefined,
          imageUrl: deriveImageUrl(item),
          capturedAt: item.captured_at ?? undefined,
          predictions,
          status: item.status,
          tags: item.tags?.map((tag) => ({ id: tag.id, name: tag.name, confidence: tag.confidence })) ?? [],
          sceneAttributes: item.scene_attributes,
          metadataSource: item.metadata_source,
          matchConfidence: item.match_confidence,
          predictedTimestamp: item.predicted_timestamp ?? undefined,
          predictedShotId: item.predicted_shot_id ?? undefined,
          shotTimestamp: item.shot_timestamp ?? undefined,
          sceneSummary: item.scene_summary ?? undefined,
          actors:
            item.actor_detections?.map((actor) => ({
              id: actor.id,
              castMemberId: actor.cast_member_id,
              castMemberName: actor.cast_member_name,
              confidence: actor.confidence,
              faceIndex: actor.face_index,
              bbox: actor.bbox,
              clusterLabel: actor.cluster_label,
              trackStatus: actor.track_status,
              emotion: actor.emotion,
              poseYaw: actor.pose?.yaw ?? null,
              posePitch: actor.pose?.pitch ?? null,
              poseRoll: actor.pose?.roll ?? null,
            })) ?? [],
          embeddingModel: item.embedding_model ?? undefined,
          embeddingModelVersion: item.embedding_model_version ?? undefined,
        };
      }) ?? [],
    [data],
  );

  const [selectedFrameId, setSelectedFrameId] = useState<number | undefined>(undefined);
  const [exportSelection, setExportSelection] = useState<Set<number>>(new Set());

  useEffect(() => {
    if (frames.length && !selectedFrameId) {
      setSelectedFrameId(frames[0].id);
    } else if (selectedFrameId && !frames.find((frame) => frame.id === selectedFrameId)) {
      setSelectedFrameId(frames[0]?.id);
    }
  }, [frames, selectedFrameId]);

  useEffect(() => {
    setExportSelection((prev) => {
      const next = new Set<number>();
      frames.forEach((frame) => {
        if (prev.has(frame.id)) {
          next.add(frame.id);
        }
      });
      return next;
    });
  }, [frames]);

  const selectedFrame = frames.find((frame) => frame.id === selectedFrameId);
  const selectedForExport = frames.filter((frame) => exportSelection.has(frame.id));

  const applyOverride = (frameId: number, prediction: Prediction | string) => {
    const payload =
      typeof prediction === "string"
        ? { tags: [prediction] }
        : { tags: [prediction.title] };
    fetch(`/api/frames/${frameId}/tags`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
      },
      body: JSON.stringify(payload),
    }).then(() => mutate());
  };

  const saveSceneAttributes = (frameId: number, attributes: SceneAttribute[]) => {
    fetch(`/api/frames/${frameId}/scene-attributes`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
      },
      body: JSON.stringify({ attributes: attributes.map((attr) => ({ attribute: attr.attribute, value: attr.value, confidence: attr.confidence })) }),
    }).then(() => mutate());
  };

  const saveActorDetections = (frameId: number, actors: ActorDetection[]) => {
    fetch(`/api/frames/${frameId}/actors`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
      },
      body: JSON.stringify({
        actors: actors.map((actor) => ({
          cast_member_id: actor.castMemberId,
          confidence: actor.confidence,
          face_index: actor.faceIndex,
          bbox: actor.bbox,
          cluster_label: actor.clusterLabel,
          track_status: actor.trackStatus,
          emotion: actor.emotion,
          pose_yaw: actor.poseYaw,
          pose_pitch: actor.posePitch,
          pose_roll: actor.poseRoll,
        })),
      }),
    }).then(() => mutate());
  };

  const assignFrameToTmdb = async (frameId: number, tmdbId: number) => {
    if (!authToken) {
      throw new Error("Provide a moderator or admin token to assign a movie.");
    }
    const response = await fetch(`/api/frames/${frameId}/assign-tmdb`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${authToken}`,
      },
      body: JSON.stringify({ tmdb_id: tmdbId }),
    });
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || "Unable to assign movie.");
    }
    await mutate();
  };

  const toggleExportSelection = (frameId: number) => {
    setExportSelection((prev) => {
      const next = new Set(prev);
      if (next.has(frameId)) {
        next.delete(frameId);
      } else {
        next.add(frameId);
      }
      return next;
    });
  };

  const exportFrames = async (format: "csv" | "json") => {
    const frameIds = Array.from(exportSelection);
    if (!frameIds.length) return;
    const response = await fetch("/api/frames/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ frame_ids: frameIds, format }),
    });
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `frames.${format}`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  };

  const refreshFeed = () => {
    mutate();
  };

  const handleAuthTokenChange = (value: string) => {
    setSettingsStatus(null);
    setSettingsError(null);
    setAuthToken(value);
    if (value) {
      window.localStorage.setItem("movietagToken", value);
    } else {
      window.localStorage.removeItem("movietagToken");
    }
  };

  const ensureFrameForStorageObject = async (storageUri: string, filePath: string) => {
    if (!authToken) {
      setStorageMessage("Provide a moderator or admin token to load storage objects.");
      return;
    }
    setStorageMessage(null);
    try {
      const headers = { Authorization: `Bearer ${authToken}`, "Content-Type": "application/json" };
      let response = await fetch(`/api/frames/lookup?storage_uri=${encodeURIComponent(storageUri)}&file_path=${encodeURIComponent(filePath)}`, {
        headers,
      });

      if (response.status === 404) {
        response = await fetch("/api/frames/from-storage", {
          method: "POST",
          headers,
          body: JSON.stringify({ storage_uri: storageUri, file_path: filePath }),
        });
      }

      if (!response.ok) {
        throw new Error(await response.text());
      }

      const frame = (await response.json()) as Frame;
      await mutate();
      setSelectedFrameId(frame.id);
      setStorageMessage(`Loaded frame #${frame.id} from storage.`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to load from storage.";
      setStorageMessage(message);
    }
  };

  const saveFrameMetadata = async (frameId: number, updates: Partial<Frame>) => {
    if (!authToken) {
      setStorageMessage("Provide a moderator or admin token to save changes.");
      return;
    }
    const payload = {
      movie_id: updates.movieId,
      predicted_timestamp: updates.predictedTimestamp,
      predicted_shot_id: updates.predictedShotId,
      shot_timestamp: updates.shotTimestamp,
      scene_summary: updates.sceneSummary,
      metadata_source: updates.metadataSource,
      file_path: updates.filePath,
      storage_uri: updates.storageUri,
      match_confidence: updates.matchConfidence,
      status: updates.status,
      captured_at: updates.capturedAt,
      embedding_model: updates.embeddingModel,
      embedding_model_version: updates.embeddingModelVersion,
    };

    await fetch(`/api/frames/${frameId}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
      },
      body: JSON.stringify(payload),
    });
    await mutate();
    setStorageMessage("Saved frame changes.");
  };

  const triggerVisionAnalysis = async () => {
    if (!authToken) {
      setAnalysisMessage("Provide a moderator or admin token to run analysis.");
      return;
    }
    setAnalysisMessage(null);
    try {
      if (analysisScope === "selected") {
        if (!selectedFrameId) {
          setAnalysisMessage("Select a frame to analyze.");
          return;
        }
        const response = await fetch(`/api/frames/${selectedFrameId}/vision/run`, {
          method: "POST",
          headers: { Authorization: `Bearer ${authToken}` },
        });
        if (!response.ok) {
          throw new Error(await response.text());
        }
        const payload = await response.json();
        setAnalysisJob({ id: payload.job_id, status: "queued", processed: 0, total: 1 });
        setAnalysisMessage(`Queued analysis for frame #${selectedFrameId}.`);
        return;
      }

      const tagList = tagFilter
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean);
      const payload = {
        filters: {
          movie_id: movieFilter ? Number(movieFilter) : null,
          status: statusFilter !== "all" ? statusFilter : null,
          cast_member_id: actorFilter ? Number(actorFilter) : null,
          time_of_day: timeOfDayFilter || null,
          tag: tagList.length ? tagList : null,
        },
        limit: 2000,
      };
      const response = await fetch("/api/vision/run", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const result = await response.json();
      setAnalysisJob({ id: result.job_id, status: "queued", processed: 0, total: result.count ?? null });
      setAnalysisMessage(`Queued analysis for ${result.count ?? "matching"} frames.`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to start analysis.";
      setAnalysisMessage(message);
    }
  };

  useEffect(() => {
    if (!analysisJob || ["done", "failed"].includes(analysisJob.status)) {
      return;
    }
    const poll = async () => {
      try {
        const response = await fetch(`/api/tasks/${analysisJob.id}`);
        if (!response.ok) {
          throw new Error(await response.text());
        }
        const payload = await response.json();
        setAnalysisJob((prev) =>
          prev
            ? {
              ...prev,
              status: payload.status ?? prev.status,
              processed: payload.processed ?? prev.processed,
              total: payload.total ?? prev.total,
              error: payload.error ?? null,
            }
            : prev,
        );
        if (payload.status === "done") {
          await mutate();
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unable to fetch job status.";
        setAnalysisJob((prev) => (prev ? { ...prev, error: message } : prev));
      }
    };
    void poll();
    const interval = window.setInterval(poll, 4000);
    return () => window.clearInterval(interval);
  }, [analysisJob?.id, analysisJob?.status, mutate]);

  const filtersSummary = useMemo(() => {
    const parts: string[] = [];
    if (movieFilter) parts.push(`Movie ${movieFilter}`);
    if (tagFilter) parts.push(`Tags: ${tagFilter}`);
    if (actorFilter) parts.push(`Actor ID: ${actorFilter}`);
    if (timeOfDayFilter) parts.push(`Time: ${timeOfDayFilter}`);
    if (statusFilter !== "all") parts.push(`Status: ${statusFilter}`);
    return parts.length ? parts.join(" · ") : "All frames";
  }, [actorFilter, movieFilter, statusFilter, tagFilter, timeOfDayFilter]);

  const renderPlaceholder = (title: string, description: string) => (
    <section className="panel placeholder-panel" aria-label={`${title} view`}>
      <div className="placeholder-panel__content">
        <div>
          <p className="pill pill--primary" aria-hidden="true">
            Coming soon
          </p>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
      </div>
    </section>
  );

  return (
    <main className="page" data-testid="app-shell">
      <Sidebar selectedView={selectedView} onSelect={setSelectedView} />
      <div className="page__main">
        <Toolbar total={data?.total ?? frames.length} showing={frames.length} filtersSummary={filtersSummary} onRefresh={refreshFeed}>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <label className="label" style={{ margin: 0 }}>
              Status
            </label>
            <select
              className="select"
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value as Frame["status"] | "all")}
            >
              {statusFilters.map((filter) => (
                <option key={filter.value} value={filter.value}>
                  {filter.label}
                </option>
              ))}
            </select>
            <input
              className="input"
              placeholder="Movie ID"
              value={movieFilter}
              onChange={(event) => setMovieFilter(event.target.value)}
              style={{ minWidth: 120 }}
            />
            <input
              className="input"
              placeholder="Tags (comma-separated)"
              value={tagFilter}
              onChange={(event) => setTagFilter(event.target.value)}
              style={{ minWidth: 180 }}
            />
            <input
              className="input"
              placeholder="Actor ID"
              value={actorFilter}
              onChange={(event) => setActorFilter(event.target.value)}
              style={{ minWidth: 120 }}
            />
            <input
              className="input"
              placeholder="Time of day"
              value={timeOfDayFilter}
              onChange={(event) => setTimeOfDayFilter(event.target.value)}
              style={{ minWidth: 160 }}
            />
            {selectedFrame ? (
              <>
                <span className="pill">
                  Confidence:{" "}
                  {selectedFrame.matchConfidence !== undefined && selectedFrame.matchConfidence !== null
                    ? `${(selectedFrame.matchConfidence * 100).toFixed(1)}%`
                    : "—"}
                </span>
                <span className="pill">
                  Time: {selectedFrame.shotTimestamp || selectedFrame.predictedTimestamp || "Unknown"}
                </span>
                {selectedFrame.metadataSource ? <span className="pill">Source: {selectedFrame.metadataSource}</span> : null}
              </>
            ) : null}
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginLeft: 8 }}>
              <label className="label" style={{ margin: 0 }}>
                Vision scope
              </label>
              <select
                className="select"
                value={analysisScope}
                onChange={(event) => setAnalysisScope(event.target.value as "selected" | "filtered")}
                style={{ minWidth: 200 }}
              >
                <option value="selected">Selected frame</option>
                <option value="filtered">All frames matching filters</option>
              </select>
              <button className="button button--primary" type="button" onClick={triggerVisionAnalysis}>
                Run vision analysis
              </button>
            </div>
          </div>
        </Toolbar>

        <div className="page__content">
          {analysisJob ? (
            <section className="panel" aria-label="Vision analysis status" style={{ padding: "1rem 1.25rem" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
                <div>
                  <strong>Vision analysis job</strong>
                  <div className="muted" style={{ marginTop: 4 }}>
                    Status: {analysisJob.status}
                    {analysisJob.processed !== null && analysisJob.processed !== undefined ? (
                      <>
                        {" "}· {analysisJob.processed}
                        {analysisJob.total ? ` / ${analysisJob.total}` : ""} frames
                      </>
                    ) : null}
                  </div>
                  {analysisJob.error ? <div style={{ color: "var(--danger)" }}>{analysisJob.error}</div> : null}
                  {analysisMessage ? <div className="muted">{analysisMessage}</div> : null}
                </div>
                <span className={`chip ${analysisJob.status === "done" ? "chip--success" : "chip--muted"}`}>
                  {analysisJob.status}
                </span>
              </div>
              {analysisJob.total ? (
                <div style={{ marginTop: 12 }}>
                  <div className="progress-track">
                    <div
                      className="progress-bar"
                      style={{
                        width: `${Math.min(
                          100,
                          Math.round(((analysisJob.processed ?? 0) / analysisJob.total) * 100),
                        )}%`,
                      }}
                    />
                  </div>
                </div>
              ) : null}
            </section>
          ) : analysisMessage ? (
            <section className="panel" aria-label="Vision analysis message" style={{ padding: "1rem 1.25rem" }}>
              <p className="muted">{analysisMessage}</p>
            </section>
          ) : null}
          {selectedView === "frames" ? (
            <div className="content-grid">
              <div className="content-grid__main">
                <section className="panel" aria-label="Frame grid">
                  <FrameGrid
                    frames={frames}
                    selectedId={selectedFrameId}
                    onSelect={setSelectedFrameId}
                    selectedForExport={exportSelection}
                    onToggleSelectForExport={toggleExportSelection}
                    onEdit={setEditModalFrameId}
                  />
                </section>
              </div>
              <aside className="panel content-grid__sidebar" aria-label="Frame details" style={{ height: "100%", padding: 0 }}>
                <FrameSidebar
                  frame={selectedFrame}
                  authToken={authToken}
                  onSaveMetadata={saveFrameMetadata}
                  onApplyOverride={applyOverride}
                  onSaveScene={saveSceneAttributes}
                  onSaveActors={saveActorDetections}
                  onAssignTmdb={assignFrameToTmdb}
                >
                  <ExportPanel selectedFrames={selectedForExport} onExport={exportFrames} onClear={() => setExportSelection(new Set())} />
                </FrameSidebar>
              </aside>
            </div>
          ) : null}
          {selectedView === "storage" ? (
            <div className="content-grid content-grid--single">
              <div className="content-grid__main">
                <StorageExplorer
                  authToken={authToken}
                  onSelect={ensureFrameForStorageObject}
                  message={storageMessage}
                />
              </div>
            </div>
          ) : null}
          {selectedView === "dashboard" ? renderPlaceholder("Dashboard", "Monitor tagging throughput, queues, and automated signals in one view.") : null}
          {selectedView === "tasks" ? renderPlaceholder("Tasks", "Track review assignments, approvals, and ownership across teams.") : null}
          {selectedView === "settings" ? (
            <div className="settings-layout">
              <div className="settings-hero">
                <div>
                  <p className="eyebrow">Workspace settings</p>
                  <h2>Control access, APIs, and backend configuration</h2>
                  <p className="muted" style={{ maxWidth: 640 }}>
                    Store the tokens you use for moderation and administration, then manage storage and metadata
                    provider settings—all in one place.
                  </p>
                </div>
              </div>
              <div className="settings-grid">
                <section className="settings-card">
                  <div className="settings-card__header">
                    <div>
                      <p className="eyebrow">Access</p>
                      <h3 style={{ margin: "0.15rem 0 0.35rem" }}>Moderator & admin tokens</h3>
                      <p className="muted">
                        These tokens authenticate calls to the frame API and storage browser. They stay in your
                        browser storage until cleared.
                      </p>
                    </div>
                    {authToken ? <span className="pill pill--primary">Active</span> : <span className="pill">Not set</span>}
                  </div>
                  <div className="settings-card__body">
                    <div className="settings-grid settings-grid--two">
                      <div className="settings-field">
                        <label className="label" htmlFor="moderatorToken">
                          Moderator/Admin token
                        </label>
                        <input
                          id="moderatorToken"
                          className="input"
                          type="password"
                          placeholder="Bearer token for frame actions"
                          value={authToken}
                          onChange={(event) => handleAuthTokenChange(event.target.value)}
                        />
                        <p className="muted" style={{ margin: "0.25rem 0 0" }}>
                          Used for frame edits, storage lookups, and exports.
                        </p>
                      </div>
                    </div>
                  </div>
                  <div className="settings-card__footer">
                    <div>
                      {settingsStatus ? <p style={{ color: "var(--success)", margin: "0.4rem 0 0" }}>{settingsStatus}</p> : null}
                      {settingsError ? <p style={{ color: "var(--danger)", margin: "0.4rem 0 0" }}>{settingsError}</p> : null}
                    </div>
                    <div style={{ display: "flex", gap: 8 }}>
                      <button className="button" onClick={() => handleAuthTokenChange("")}>
                        Clear token
                      </button>
                      <button
                        className="button button--primary"
                        onClick={() => setSettingsStatus("Token saved to browser storage.")}
                        disabled={!authToken}
                      >
                        Save token
                      </button>
                    </div>
                  </div>
                </section>
                <SettingsPanel className="settings-card--full" />
                <VisionModelsPanel authToken={authToken} />
              </div>
            </div>
          ) : null}
          {selectedView === "models" ? renderPlaceholder("Models", "Manage pipelines, versions, and rollout strategies for inference.") : null}
          {selectedView === "support" ? renderPlaceholder("Support", "Reach the help desk, docs, and operational runbooks.") : null}
        </div>
      </div>

      <FrameEditModal
        frame={frames.find(f => f.id === editModalFrameId)}
        isOpen={editModalFrameId !== null}
        onClose={() => setEditModalFrameId(null)}
        onSaveMetadata={saveFrameMetadata}
        onApplyOverride={applyOverride}
        onSaveScene={saveSceneAttributes}
        onSaveActors={saveActorDetections}
        onAssignTmdb={assignFrameToTmdb}
        authToken={authToken}
      />
    </main>
  );
}
