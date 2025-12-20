/* eslint-disable @next/next/no-img-element */
"use client";

import { useEffect, useMemo, useState } from "react";
import useSWR from "swr";
import { ActorDetection, Frame, Prediction, SceneAttribute } from "../lib/types";
import { FrameDetailsPanel } from "../components/FrameDetailsPanel";
import { FrameGrid } from "../components/FrameGrid";
import { OverrideForm } from "../components/OverrideForm";
import { Toolbar } from "../components/Toolbar";
import { SceneAttributesForm } from "../components/SceneAttributesForm";
import { ActorDetectionsForm } from "../components/ActorDetectionsForm";
import { ExportPanel } from "../components/ExportPanel";

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
  predicted_movie_id?: number | null;
  predicted_movie_title?: string | null;
  predicted_timestamp?: string | null;
  predicted_shot_id?: string | null;
  shot_timestamp?: string | null;
  scene_summary?: string | null;
  metadata_source?: string | null;
  match_confidence?: number | null;
  tags?: { id: number; name: string; confidence?: number }[];
  scene_attributes?: { id: number; attribute: string; value: string; confidence?: number }[];
  actor_detections?: {
    id: number;
    cast_member_id: number | null;
    cast_member_name?: string | null;
    confidence?: number;
    face_index?: number | null;
    bbox?: number[] | null;
  }[];
};

type FramesApiResponse = { items: FrameApiItem[]; total: number };

const fetcher = (url: string) => fetch(url).then((res) => res.json());

export default function Home() {
  const [movieFilter, setMovieFilter] = useState("");
  const [tagFilter, setTagFilter] = useState("");
  const [actorFilter, setActorFilter] = useState("");
  const [timeOfDayFilter, setTimeOfDayFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<Frame["status"] | "all">("all");

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

  const { data, mutate } = useSWR<FramesApiResponse>(framesUrl, fetcher, {
    revalidateOnFocus: false,
  });

  const frames: Frame[] = useMemo(
    () =>
      data?.items.map((item) => {
        const predictions: Prediction[] =
          item.predicted_movie_id !== null && item.predicted_movie_id !== undefined
            ? [
                {
                  source: item.metadata_source || "match-model",
                  title: item.predicted_movie_title ?? `Movie #${item.predicted_movie_id}`,
                  confidence: item.match_confidence ?? 0,
                },
              ]
            : [];

        return {
          id: item.id,
          movieId: item.movie_id,
          movieTitle:
            item.movie_title || item.predicted_movie_title || (item.movie_id ? `Movie #${item.movie_id}` : "Unknown movie"),
          predictedMovieId: item.predicted_movie_id,
          predictedMovieTitle: item.predicted_movie_title,
          imageUrl: item.signed_url || item.file_path,
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
            })) ?? [],
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
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then(() => mutate());
  };

  const saveSceneAttributes = (frameId: number, attributes: SceneAttribute[]) => {
    fetch(`/api/frames/${frameId}/scene-attributes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ attributes: attributes.map((attr) => ({ attribute: attr.attribute, value: attr.value, confidence: attr.confidence })) }),
    }).then(() => mutate());
  };

  const saveActorDetections = (frameId: number, actors: ActorDetection[]) => {
    fetch(`/api/frames/${frameId}/actors`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        actors: actors.map((actor) => ({
          cast_member_id: actor.castMemberId,
          confidence: actor.confidence,
          face_index: actor.faceIndex,
          bbox: actor.bbox,
        })),
      }),
    }).then(() => mutate());
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

  const filtersSummary = useMemo(() => {
    const parts: string[] = [];
    if (movieFilter) parts.push(`Movie ${movieFilter}`);
    if (tagFilter) parts.push(`Tags: ${tagFilter}`);
    if (actorFilter) parts.push(`Actor ID: ${actorFilter}`);
    if (timeOfDayFilter) parts.push(`Time: ${timeOfDayFilter}`);
    if (statusFilter !== "all") parts.push(`Status: ${statusFilter}`);
    return parts.length ? parts.join(" · ") : "All frames";
  }, [actorFilter, movieFilter, statusFilter, tagFilter, timeOfDayFilter]);

  return (
    <main className="page">
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
        </div>
      </Toolbar>

      <div className="page__content">
        <section className="panel" aria-label="Frame grid">
          <FrameGrid
            frames={frames}
            selectedId={selectedFrameId}
            onSelect={setSelectedFrameId}
            selectedForExport={exportSelection}
            onToggleSelectForExport={toggleExportSelection}
          />
        </section>
        <aside className="panel" aria-label="Frame details">
          <FrameDetailsPanel frame={selectedFrame} />
          <OverrideForm frame={selectedFrame} onApply={applyOverride} />
          <SceneAttributesForm frame={selectedFrame} onSave={saveSceneAttributes} />
          <ActorDetectionsForm frame={selectedFrame} onSave={saveActorDetections} />
          <ExportPanel selectedFrames={selectedForExport} onExport={exportFrames} onClear={() => setExportSelection(new Set())} />
        </aside>
      </div>
    </main>
  );
}
