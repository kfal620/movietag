import Image from "next/image";
import { Frame } from "../lib/types";
import { PredictionList } from "./PredictionList";

type Props = {
  frame?: Frame;
};

export function FrameDetailsPanel({ frame }: Props) {
  if (!frame) {
    return (
      <div className="empty-state">
        Choose a frame from the grid to inspect predictions and metadata.
      </div>
    );
  }

  return (
    <div className="sidebar">
      <div className="sidebar__section">
        <div style={{ position: "relative", width: "100%", height: 200, borderRadius: 12, overflow: "hidden" }}>
          <Image src={frame.imageUrl} alt={frame.movieTitle} fill style={{ objectFit: "cover" }} />
        </div>
        <h3 className="sidebar__title" style={{ marginTop: "0.9rem" }}>
          {frame.movieTitle}
        </h3>
        <p style={{ color: "var(--muted)", marginTop: "0.3rem" }}>Status: {frame.status.replace("_", " ")}</p>
        {frame.metadataSource ? (
          <p style={{ color: "var(--muted)", marginTop: "0.35rem" }}>
            Metadata source <strong>{frame.metadataSource}</strong>
          </p>
        ) : null}
        {frame.ingestSource ? (
          <p style={{ color: "var(--muted)", marginTop: "0.35rem" }}>
            Ingested from <strong>{frame.ingestSource}</strong>
          </p>
        ) : null}
        <div className="meta-grid" style={{ marginTop: "0.8rem" }}>
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
    </div>
  );
}
