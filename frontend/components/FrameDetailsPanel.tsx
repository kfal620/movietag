import Image from "next/image";
import { useEffect, useState } from "react";
import { Frame, TmdbSearchResult } from "../lib/types";
import { PredictionList } from "./PredictionList";

type Props = {
  frame?: Frame;
  authToken?: string;
  onAssignTmdb?: (frameId: number, tmdbId: number) => Promise<void>;
};

export function FrameDetailsPanel({ frame, authToken, onAssignTmdb }: Props) {
  const [searchQuery, setSearchQuery] = useState("");
  const [searchYear, setSearchYear] = useState("");
  const [searchResults, setSearchResults] = useState<TmdbSearchResult[]>([]);
  const [selectedTmdbId, setSelectedTmdbId] = useState<number | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [searching, setSearching] = useState(false);
  const [assigning, setAssigning] = useState(false);
  const [assignMessage, setAssignMessage] = useState<string | null>(null);

  if (!frame) return null;

  useEffect(() => {
    setSearchQuery("");
    setSearchYear("");
    setSearchResults([]);
    setSelectedTmdbId(null);
    setSearchError(null);
    setAssignMessage(null);
  }, [frame?.id]);

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
    if (!onAssignTmdb) return;
    setAssigning(true);
    setAssignMessage(null);
    try {
      await onAssignTmdb(frame.id, selectedTmdbId);
      setAssignMessage("Frame assigned to the selected movie.");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Assignment failed";
      setAssignMessage(message);
    } finally {
      setAssigning(false);
    }
  };

  return (
    <>
      <div className="sidebar__section">
        {/* Header moved to FrameSidebar */}

        <div className="meta-grid" style={{ marginTop: "0.8rem" }}>
          <div className="meta-box">
            <label>Assigned movie</label>
            <strong>{frame.movieTitle || frame.predictedMovieTitle || "Unassigned"}</strong>
          </div>
          <div className="meta-box">
            <label>Predicted match</label>
            <strong>{frame.predictedMovieTitle || "—"}</strong>
          </div>
          <div className="meta-box">
            <label>Confidence</label>
            <strong>{frame.matchConfidence !== null && frame.matchConfidence !== undefined ? `${(frame.matchConfidence * 100).toFixed(1)}%` : "—"}</strong>
          </div>
          <div className="meta-box">
            <label>Timestamp</label>
            <strong>{frame.shotTimestamp || frame.predictedTimestamp || "Unknown"}</strong>
          </div>
          <div className="meta-box">
            <label>Shot ID</label>
            <strong>{frame.predictedShotId || "—"}</strong>
          </div>
          <div className="meta-box">
            <label>Scene summary</label>
            <strong>{frame.sceneSummary || "Unknown"}</strong>
          </div>
          <div className="meta-box">
            <label>File path</label>
            <strong style={{ wordBreak: "break-all" }}>{frame.filePath}</strong>
          </div>
          <div className="meta-box">
            <label>Storage URI</label>
            <strong style={{ wordBreak: "break-all" }}>{frame.storageUri || "—"}</strong>
          </div>
          <div className="meta-box">
            <label>Tags</label>
            <strong>
              {frame.tags?.length
                ? frame.tags.map((tag) => `${tag.name}${tag.confidence ? ` (${(tag.confidence * 100).toFixed(1)}%)` : ""}`).join(", ")
                : "Unlabeled"}
            </strong>
          </div>
        </div>
      </div>

      <div className="sidebar__section">
        <h4>Manually assign via TMDb</h4>
        <p className="muted" style={{ marginTop: -6 }}>
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
        {searchError ? <p style={{ color: "var(--danger)" }}>{searchError}</p> : null}
        {searchResults.length ? (
          <div className="list" style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 8 }}>
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
                  className="card"
                  role="button"
                  tabIndex={0}
                  onClick={() => setSelectedTmdbId(result.tmdb_id)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      setSelectedTmdbId(result.tmdb_id);
                    }
                  }}
                  style={{
                    display: "flex",
                    gap: 12,
                    border: isSelected ? "2px solid var(--primary)" : "1px solid var(--border)",
                    background: isSelected ? "rgba(59, 130, 246, 0.08)" : undefined,
                    cursor: "pointer",
                    padding: 8,
                  }}
                >
                  <div style={{ position: "relative", width: 60, height: 90, flexShrink: 0 }}>
                    <Image src={posterUrl} alt={result.title} fill style={{ objectFit: "cover", borderRadius: 6 }} sizes="60px" />
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 4 }}>
                      <strong>{result.title}</strong>
                      <span className="chip chip--muted">{result.release_year ?? "Unknown year"}</span>
                    </div>
                    <p className="muted" style={{ margin: 0, lineHeight: 1.4 }}>
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

      <div className="sidebar__section">
        <h4>Model predictions</h4>
        <PredictionList predictions={frame.predictions} approvedPrediction={frame.approvedPrediction} />
      </div>

      <div className="sidebar__section">
        <h4>Scene attributes</h4>
        {frame.sceneAttributes?.length ? (
          <ul className="list">
            {frame.sceneAttributes.map((attr) => (
              <li key={`${attr.attribute}-${attr.value}`} className="list__item">
                <strong>{attr.attribute}</strong>: {attr.value}{" "}
                {attr.confidence !== undefined ? (
                  <span className="chip chip--muted">{(attr.confidence * 100).toFixed(1)}%</span>
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No scene annotations</p>
        )}
      </div>

      <div className="sidebar__section">
        <h4>Actor detections</h4>
        {frame.actors?.length ? (
          <ul className="list">
            {frame.actors.map((actor) => (
              <li key={`${actor.castMemberId}-${actor.faceIndex ?? "unknown"}`} className="list__item">
                <div>
                  <strong>{actor.castMemberName || `Cast member #${actor.castMemberId ?? "?"}`}</strong>
                  {actor.faceIndex !== undefined && actor.faceIndex !== null ? (
                    <span style={{ marginLeft: 8 }}>Face #{actor.faceIndex}</span>
                  ) : null}
                  {actor.clusterLabel ? (
                    <span style={{ marginLeft: 8 }} className="chip chip--muted">
                      {actor.clusterLabel}
                    </span>
                  ) : null}
                  {actor.trackStatus ? (
                    <span style={{ marginLeft: 8, color: "var(--muted)" }}>
                      {actor.trackStatus}
                    </span>
                  ) : null}
                </div>
                {actor.confidence !== undefined ? (
                  <span className="chip chip--muted">{(actor.confidence * 100).toFixed(1)}%</span>
                ) : null}
                {actor.emotion ? <div className="muted">Emotion: {actor.emotion}</div> : null}
                {actor.poseYaw !== undefined || actor.posePitch !== undefined || actor.poseRoll !== undefined ? (
                  <div className="muted">
                    Pose {actor.poseYaw ?? "—"}/{actor.posePitch ?? "—"}/{actor.poseRoll ?? "—"}
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No actors detected</p>
        )}
      </div>

      {frame.overrideTitle ? (
        <div className="sidebar__section">
          <h4>Override</h4>
          <p>
            <strong>{frame.overrideTitle}</strong>
          </p>
          <p className="chip">Awaiting sync</p>
        </div>
      ) : null}
    </>
  );
}
