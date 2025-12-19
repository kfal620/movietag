import { Prediction } from "../lib/types";

type Props = {
  predictions: Prediction[];
  approvedPrediction?: Prediction;
};

export function PredictionList({ predictions, approvedPrediction }: Props) {
  return (
    <div className="predictions">
      {predictions.map((prediction) => {
        const isApproved =
          approvedPrediction &&
          approvedPrediction.title === prediction.title &&
          approvedPrediction.source === prediction.source;

        return (
          <div key={`${prediction.source}-${prediction.title}`} className="prediction">
            <div className="prediction__meta">
              <span className="prediction__title">
                {prediction.title} {prediction.year ? `(${prediction.year})` : ""}
              </span>
              <span className="prediction__subtitle">Model: {prediction.source}</span>
            </div>
            <div className="chip chip--muted">
              {(prediction.confidence * 100).toFixed(1)}%
            </div>
            {isApproved ? <div className="chip chip--success">Approved</div> : null}
          </div>
        );
      })}
    </div>
  );
}
