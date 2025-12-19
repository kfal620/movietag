import Image from "next/image";
import { Frame } from "../lib/types";

type Props = {
  frame: Frame;
  isActive: boolean;
  onSelect: (frameId: number) => void;
};

const statusBadge = {
  pending: { label: "Pending", className: "badge" },
  new: { label: "New", className: "badge badge--warning" },
  needs_review: { label: "Needs review", className: "badge badge--danger" },
  confirmed: { label: "Confirmed", className: "badge badge--success" },
  overridden: { label: "Overridden", className: "badge" },
  tagged: { label: "Tagged", className: "badge badge--success" },
  embedded: { label: "Embedded", className: "badge" },
  scene_annotated: { label: "Scene ready", className: "badge" },
  actors_detected: { label: "Actors detected", className: "badge badge--success" },
} as const;

export function FrameCard({ frame, isActive, onSelect }: Props) {
  const badge = statusBadge[frame.status] ?? statusBadge.pending;

  return (
    <article
      className="card"
      aria-pressed={isActive}
      role="button"
      onClick={() => onSelect(frame.id)}
      style={isActive ? { borderColor: "rgba(96, 165, 250, 0.6)" } : undefined}
    >
      <div className="card__image">
        <Image src={frame.imageUrl} alt={frame.movieTitle} fill sizes="320px" />
        <span className={badge.className}>{badge.label}</span>
        <div className="card__overlay">
          <span>{frame.movieTitle}</span>
          <small className="card__meta">{frame.sceneTime}</small>
        </div>
      </div>
      <div className="card__meta">
        <h3>{frame.movieTitle}</h3>
        <span>{frame.ingestSource}</span>
        <div className="status-row">
          <div
            className={`status-dot ${
              frame.status === "confirmed"
                ? "status-dot--success"
                : frame.status === "needs_review"
                  ? "status-dot--danger"
                  : frame.status === "overridden"
                    ? "status-dot--warning"
                    : ""
            }`}
          />
          {frame.tags?.length ? <span className="chip chip--muted">{frame.tags.join(", ")}</span> : null}
        </div>
      </div>
    </article>
  );
}
