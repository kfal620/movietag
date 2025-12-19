import { useMemo, useState } from "react";
import { Frame, Prediction } from "../lib/types";

type Props = {
  frame?: Frame;
  onApply: (frameId: string, prediction: Prediction | string) => void;
};

export function OverrideForm({ frame, onApply }: Props) {
  const [overrideTitle, setOverrideTitle] = useState("");
  const [selectedModelPrediction, setSelectedModelPrediction] = useState<string>("");
  const [notes, setNotes] = useState("");

  const selectedPrediction = useMemo(() => {
    if (!frame) return undefined;
    return frame.predictions.find(
      (prediction) =>
        `${prediction.source}-${prediction.title}` === selectedModelPrediction,
    );
  }, [frame, selectedModelPrediction]);

  if (!frame) {
    return (
      <div className="empty-state">
        Select a frame to review predictions and apply overrides.
      </div>
    );
  }

  const handleApply = () => {
    if (selectedPrediction) {
      onApply(frame.id, selectedPrediction);
      setSelectedModelPrediction("");
    } else if (overrideTitle.trim()) {
      onApply(frame.id, overrideTitle.trim());
      setOverrideTitle("");
    }
    setNotes("");
  };

  return (
    <div className="sidebar__section" aria-live="polite">
      <h4>Apply override</h4>
      <label className="label" htmlFor="predictionSelect">
        Choose a model prediction
      </label>
      <select
        id="predictionSelect"
        className="select"
        value={selectedModelPrediction}
        onChange={(event) => setSelectedModelPrediction(event.target.value)}
      >
        <option value="">Select prediction...</option>
        {frame.predictions.map((prediction) => (
          <option key={`${prediction.source}-${prediction.title}`} value={`${prediction.source}-${prediction.title}`}>
            {prediction.title} ({(prediction.confidence * 100).toFixed(1)}% · {prediction.source})
          </option>
        ))}
      </select>

      <div style={{ margin: "1rem 0 0.5rem" }}>
        <span className="label">Or enter a manual override</span>
        <input
          className="input"
          placeholder="Movie title or identifier"
          value={overrideTitle}
          onChange={(event) => setOverrideTitle(event.target.value)}
        />
      </div>

      <label className="label" htmlFor="notes" style={{ marginTop: "0.75rem" }}>
        Notes (optional)
      </label>
      <textarea
        id="notes"
        className="input"
        style={{ minHeight: 90, resize: "vertical" }}
        value={notes}
        onChange={(event) => setNotes(event.target.value)}
        placeholder="Confidence, source, or why you are overriding."
      />

      <button className="button button--primary" style={{ marginTop: "1rem", width: "100%" }} onClick={handleApply}>
        Save override
      </button>
    </div>
  );
}
