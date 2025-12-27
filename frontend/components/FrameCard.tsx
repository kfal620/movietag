import Image from "next/image";
import { Frame } from "../lib/types";

type Props = {
  frame: Frame;
  isActive: boolean;
  onSelect: (frameId: number) => void;
  selectedForExport?: boolean;
  onToggleSelect?: (frameId: number) => void;
  onEdit?: (frameId: number) => void;
};

const statusBadge = {
  needs_analyzing: { label: "Needs Analyzing", className: "badge badge--warning" },
  analyzed: { label: "Analyzed", className: "badge badge--success" },
  tmdb_only: { label: "TMDB Only", className: "badge" },
  confirmed: { label: "Confirmed", className: "badge badge--success" },
  pending: { label: "Pending", className: "badge" },
} as const;

export function FrameCard({ frame, isActive, onSelect, selectedForExport, onToggleSelect, onEdit }: Props) {
  const badge = statusBadge[frame.status] ?? statusBadge.pending;
  const timeOfDay = frame.sceneAttributes?.find((attr) => attr.attribute === "time_of_day")?.value;
  const environment = frame.sceneAttributes?.find((attr) => attr.attribute === "environment")?.value;
  const actorsCount = frame.actors?.length ?? 0;

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
        {onEdit && (
          <button
            className="button button--ghost"
            style={{
              position: "absolute",
              top: 8,
              left: 8,
              background: 'rgba(0,0,0,0.7)',
              color: 'white',
              backdropFilter: 'blur(4px)',
              border: '1px solid rgba(255,255,255,0.2)',
              padding: '0.25rem 0.5rem',
              fontSize: '0.75rem'
            }}
            onClick={(event) => {
              event.stopPropagation();
              onEdit(frame.id);
            }}
          >
            Edit
          </button>
        )}
        {onToggleSelect ? (
          <label className="chip chip--muted" style={{ position: "absolute", top: 35, right: 8 }}>
            <input
              type="checkbox"
              aria-label={`Toggle export selection for frame ${frame.id}`}
              checked={selectedForExport}
              onClick={(event) => event.stopPropagation()}
              onChange={() => onToggleSelect(frame.id)}
            />{" "}
            Export
          </label>
        ) : null}
        <div className="card__overlay">
          <span>{frame.movieTitle}</span>
        </div>
      </div>
      <div className="card__meta">
        <h3>{frame.movieTitle}</h3>
        <span>{frame.metadataSource || frame.ingestSource || "Unspecified source"}</span>
        <div className="status-row">
          <div
            className={`status-dot ${frame.status === "confirmed" || frame.status === "analyzed"
                ? "status-dot--success"
                : frame.status === "needs_analyzing"
                  ? "status-dot--danger"
                  : "status-dot--warning"
              }`}
          />
          {frame.tags?.length ? (
            <span className="chip chip--muted">
              {frame.tags.map((tag) => tag.name).join(", ")}
            </span>
          ) : null}
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem" }}>
          {timeOfDay ? <span className="chip chip--muted">{timeOfDay}</span> : null}
          {environment ? <span className="chip chip--muted">{environment}</span> : null}
          <span className="chip chip--muted">{actorsCount} actors</span>
        </div>
      </div>
    </article>
  );
}
