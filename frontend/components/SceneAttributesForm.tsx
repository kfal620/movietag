import { useEffect, useState } from "react";
import { Frame, SceneAttribute } from "../lib/types";

type Props = {
  frame?: Frame;
  onSave: (frameId: number, attributes: SceneAttribute[]) => void;
};

export function SceneAttributesForm({ frame, onSave }: Props) {
  const [rows, setRows] = useState<SceneAttribute[]>([]);

  useEffect(() => {
    setRows(frame?.sceneAttributes ?? []);
  }, [frame]);

  if (!frame) {
    return (
      <div className="empty-state">
        Select a frame to review and approve scene metadata.
      </div>
    );
  }

  const updateRow = (index: number, key: keyof SceneAttribute, value: string) => {
    setRows((prev) => {
      const next = [...prev];
      const updated = { ...next[index], [key]: value };
      if (key === "confidence") {
        const parsed = Number(value);
        updated.confidence = Number.isNaN(parsed) ? undefined : parsed;
      }
      next[index] = updated;
      return next;
    });
  };

  const addRow = () => setRows((prev) => [...prev, { attribute: "", value: "" }]);
  const removeRow = (index: number) => setRows((prev) => prev.filter((_, idx) => idx !== index));

  const handleSave = () => {
    onSave(frame.id, rows.filter((row) => row.attribute && row.value));
  };

  return (
    <div className="sidebar__section" aria-live="polite">
      <h4>Scene attributes</h4>
      <p className="muted">
        Approve or override scene attributes detected by the model. Include a confidence if available.
      </p>
      {rows.map((row, index) => (
        <div key={`${row.attribute}-${index}`} className="meta-grid" style={{ marginBottom: "0.5rem" }}>
          <div className="meta-box" style={{ width: "100%" }}>
            <label>Attribute</label>
            <input
              className="input"
              value={row.attribute}
              onChange={(event) => updateRow(index, "attribute", event.target.value)}
              placeholder="time_of_day"
            />
          </div>
          <div className="meta-box" style={{ width: "100%" }}>
            <label>Value</label>
            <input
              className="input"
              value={row.value}
              onChange={(event) => updateRow(index, "value", event.target.value)}
              placeholder="night"
            />
          </div>
          <div className="meta-box" style={{ width: "100%" }}>
            <label>Confidence</label>
            <input
              className="input"
              value={row.confidence ?? ""}
              onChange={(event) => updateRow(index, "confidence", event.target.value)}
              placeholder="0.92"
            />
          </div>
          <button className="button" type="button" onClick={() => removeRow(index)}>
            Remove
          </button>
        </div>
      ))}

      <div style={{ display: "flex", gap: 8 }}>
        <button className="button" type="button" onClick={addRow}>
          Add attribute
        </button>
        <button className="button button--primary" type="button" onClick={handleSave}>
          Save scene metadata
        </button>
      </div>
    </div>
  );
}
