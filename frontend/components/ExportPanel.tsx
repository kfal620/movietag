import { Frame } from "../lib/types";

type Props = {
  selectedFrames: Frame[];
  onExport: (format: "csv" | "json") => Promise<void> | void;
  onClear: () => void;
};

export function ExportPanel({ selectedFrames, onExport, onClear }: Props) {
  return (
    <div className="sidebar__section">
      <h4>Export selected frames</h4>
      <p className="muted">
        Package metadata for the frames you have selected in the grid. Use this to share reviews or archive
        moderation results.
      </p>
      <div className="pill" style={{ marginBottom: 8 }}>
        <strong>{selectedFrames.length}</strong> frames ready for export
      </div>
      {selectedFrames.length ? (
        <ul className="list" style={{ maxHeight: 140, overflow: "auto" }}>
          {selectedFrames.map((frame) => (
            <li key={frame.id} className="list__item">
              #{frame.id} · {frame.movieTitle}
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">Select frames from the grid to enable export.</p>
      )}
      <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
        <button className="button" disabled={!selectedFrames.length} onClick={() => onExport("csv")}>
          Download CSV
        </button>
        <button className="button" disabled={!selectedFrames.length} onClick={() => onExport("json")}>
          Download JSON
        </button>
        <button className="button" onClick={onClear}>
          Clear
        </button>
      </div>
    </div>
  );
}
