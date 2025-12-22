import { useEffect, useState } from "react";
import { Frame } from "../lib/types";

type Props = {
  frame?: Frame;
  onSave: (frameId: number, updates: Partial<Frame>) => void;
};

export function FrameMetadataForm({ frame, onSave }: Props) {
  const [draft, setDraft] = useState<Partial<Frame>>({});

  useEffect(() => {
    if (frame) {
      setDraft({
        movieId: frame.movieId,
        predictedMovieId: frame.predictedMovieId,
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
    } else {
      setDraft({});
    }
  }, [frame]);

  if (!frame) {
    return (
      <div className="empty-state">
        Select a frame to edit its metadata.
      </div>
    );
  }

  const update = (key: keyof Frame, value: string) => {
    setDraft((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <div className="sidebar__section" aria-live="polite">
      <h4>Frame metadata</h4>
      <p className="muted">Edit the core attributes of this frame, including its storage location and movie linkage.</p>

      <label className="label" htmlFor="movieId">Movie ID</label>
      <input
        id="movieId"
        className="input"
        value={draft.movieId ?? ""}
        onChange={(event) => setDraft((prev) => ({ ...prev, movieId: event.target.value ? Number(event.target.value) : null }))}
        placeholder="123"
      />

      <label className="label" htmlFor="predictedMovieId" style={{ marginTop: 8 }}>Predicted movie ID</label>
      <input
        id="predictedMovieId"
        className="input"
        value={draft.predictedMovieId ?? ""}
        onChange={(event) => setDraft((prev) => ({ ...prev, predictedMovieId: event.target.value ? Number(event.target.value) : null }))}
        placeholder="Predicted movie"
      />

      <label className="label" htmlFor="status" style={{ marginTop: 8 }}>Status</label>
      <select
        id="status"
        className="select"
        value={draft.status}
        onChange={(event) => update("status", event.target.value)}
      >
        <option value="pending">Pending</option>
        <option value="new">New</option>
        <option value="needs_review">Needs review</option>
        <option value="confirmed">Confirmed</option>
        <option value="overridden">Overridden</option>
        <option value="tagged">Tagged</option>
        <option value="embedded">Embedded</option>
        <option value="scene_annotated">Scene annotated</option>
        <option value="actors_detected">Actors detected</option>
      </select>

      <label className="label" htmlFor="filePath" style={{ marginTop: 8 }}>File path</label>
      <input
        id="filePath"
        className="input"
        value={draft.filePath ?? ""}
        onChange={(event) => update("filePath", event.target.value)}
        placeholder="frames/clip/image.jpg"
      />

      <label className="label" htmlFor="storageUri" style={{ marginTop: 8 }}>Storage URI</label>
      <input
        id="storageUri"
        className="input"
        value={draft.storageUri ?? ""}
        onChange={(event) => update("storageUri", event.target.value)}
        placeholder="s3://frames/key.jpg"
      />

      <label className="label" htmlFor="capturedAt" style={{ marginTop: 8 }}>Captured at</label>
      <input
        id="capturedAt"
        className="input"
        value={draft.capturedAt ?? ""}
        onChange={(event) => update("capturedAt", event.target.value)}
        placeholder="2024-06-01T12:30:00Z"
      />

      <div className="meta-grid" style={{ marginTop: 8 }}>
        <div className="meta-box">
          <label>Predicted timestamp</label>
          <input
            className="input"
            value={draft.predictedTimestamp ?? ""}
            onChange={(event) => update("predictedTimestamp", event.target.value)}
            placeholder="00:10:12.345"
          />
        </div>
        <div className="meta-box">
          <label>Shot timestamp</label>
          <input
            className="input"
            value={draft.shotTimestamp ?? ""}
            onChange={(event) => update("shotTimestamp", event.target.value)}
            placeholder="00:10:10.000"
          />
        </div>
        <div className="meta-box">
          <label>Predicted shot ID</label>
          <input
            className="input"
            value={draft.predictedShotId ?? ""}
            onChange={(event) => update("predictedShotId", event.target.value)}
            placeholder="shot-123"
          />
        </div>
      </div>

      <label className="label" htmlFor="matchConfidence" style={{ marginTop: 8 }}>Match confidence</label>
      <input
        id="matchConfidence"
        className="input"
        value={draft.matchConfidence ?? ""}
        onChange={(event) =>
          setDraft((prev) => ({ ...prev, matchConfidence: event.target.value === "" ? undefined : Number(event.target.value) }))
        }
        placeholder="0.93"
      />

      <label className="label" htmlFor="metadataSource" style={{ marginTop: 8 }}>Metadata source</label>
      <input
        id="metadataSource"
        className="input"
        value={draft.metadataSource ?? ""}
        onChange={(event) => update("metadataSource", event.target.value)}
        placeholder="human-review"
      />

      <label className="label" htmlFor="sceneSummary" style={{ marginTop: 8 }}>Scene summary</label>
      <textarea
        id="sceneSummary"
        className="input"
        style={{ minHeight: 80 }}
        value={draft.sceneSummary ?? ""}
        onChange={(event) => update("sceneSummary", event.target.value)}
        placeholder="Short description of the shot."
      />

      <button
        className="button button--primary"
        style={{ marginTop: "1rem", width: "100%" }}
        onClick={() => onSave(frame.id, draft)}
      >
        Save metadata
      </button>
    </div>
  );
}
