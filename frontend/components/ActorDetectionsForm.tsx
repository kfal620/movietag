import { useEffect, useState } from "react";
import { ActorDetection, Frame } from "../lib/types";

type Props = {
  frame?: Frame;
  onSave: (frameId: number, detections: ActorDetection[]) => void;
};

const emptyDetection: ActorDetection = { castMemberId: null, confidence: undefined, faceIndex: undefined };

export function ActorDetectionsForm({ frame, onSave }: Props) {
  const [rows, setRows] = useState<ActorDetection[]>([]);

  useEffect(() => {
    setRows(frame?.actors ?? []);
  }, [frame]);

  if (!frame) {
    return (
      <div className="empty-state">
        Choose a frame to moderate actor detections.
      </div>
    );
  }

  const updateRow = (index: number, key: keyof ActorDetection, value: string) => {
    setRows((prev) => {
      const next = [...prev];
      const updated = { ...next[index] };
      if (key === "castMemberId") {
        updated.castMemberId = value === "" ? null : Number(value);
      } else if (key === "confidence") {
        updated.confidence = value === "" ? undefined : Number(value);
      } else if (key === "faceIndex") {
        updated.faceIndex = value === "" ? undefined : Number(value);
      } else if (key === "bbox") {
        updated.bbox = value
          .split(",")
          .map((piece) => Number(piece.trim()))
          .filter((num) => !Number.isNaN(num));
      }
      next[index] = updated;
      return next;
    });
  };

  const addRow = () => setRows((prev) => [...prev, { ...emptyDetection }]);
  const removeRow = (index: number) => setRows((prev) => prev.filter((_, idx) => idx !== index));

  const handleSave = () => {
    onSave(frame.id, rows.filter((row) => row.castMemberId !== null || row.confidence !== undefined));
  };

  return (
    <div className="sidebar__section" aria-live="polite">
      <h4>Actor detections</h4>
      <p className="muted">
        Approve or override detected actors. Provide cast member IDs to ground detections to known people.
      </p>
      {rows.map((row, index) => (
        <div key={`${row.castMemberId}-${index}`} className="meta-grid" style={{ marginBottom: "0.5rem" }}>
          <div className="meta-box" style={{ width: "100%" }}>
            <label>Cast member ID</label>
            <input
              className="input"
              value={row.castMemberId ?? ""}
              onChange={(event) => updateRow(index, "castMemberId", event.target.value)}
              placeholder="123"
            />
          </div>
          <div className="meta-box" style={{ width: "100%" }}>
            <label>Face index</label>
            <input
              className="input"
              value={row.faceIndex ?? ""}
              onChange={(event) => updateRow(index, "faceIndex", event.target.value)}
              placeholder="0"
            />
          </div>
          <div className="meta-box" style={{ width: "100%" }}>
            <label>Confidence</label>
            <input
              className="input"
              value={row.confidence ?? ""}
              onChange={(event) => updateRow(index, "confidence", event.target.value)}
              placeholder="0.85"
            />
          </div>
          <div className="meta-box" style={{ width: "100%" }}>
            <label>BBox (comma separated)</label>
            <input
              className="input"
              value={row.bbox?.join(",") ?? ""}
              onChange={(event) => updateRow(index, "bbox", event.target.value)}
              placeholder="x1,y1,x2,y2"
            />
          </div>
          <button className="button" type="button" onClick={() => removeRow(index)}>
            Remove
          </button>
        </div>
      ))}

      <div style={{ display: "flex", gap: 8 }}>
        <button className="button" type="button" onClick={addRow}>
          Add actor
        </button>
        <button className="button button--primary" type="button" onClick={handleSave}>
          Save actors
        </button>
      </div>
    </div>
  );
}
