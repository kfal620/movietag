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
        <p style={{ color: "var(--muted)", marginTop: "0.3rem" }}>{frame.sceneTime}</p>
        <p style={{ color: "var(--muted)", marginTop: "0.35rem" }}>
          Ingested from <strong>{frame.ingestSource}</strong>
        </p>
        <div className="meta-grid" style={{ marginTop: "0.8rem" }}>
          <div className="meta-box">
            <label>Top prediction</label>
            <strong>{frame.predictions[0]?.title ?? "—"}</strong>
          </div>
          <div className="meta-box">
            <label>Status</label>
            <strong>{frame.status.replace("_", " ")}</strong>
          </div>
          <div className="meta-box">
            <label>Tags</label>
            <strong>{frame.tags?.join(", ") || "Unlabeled"}</strong>
          </div>
        </div>
      </div>

      <div className="sidebar__section">
        <h4>Model predictions</h4>
        <PredictionList predictions={frame.predictions} approvedPrediction={frame.approvedPrediction} />
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
