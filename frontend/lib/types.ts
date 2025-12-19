export type Prediction = {
  source: string;
  title: string;
  confidence: number;
  year?: number;
};

export type Frame = {
  id: string;
  movieTitle: string;
  imageUrl: string;
  sceneTime: string;
  ingestSource: string;
  predictions: Prediction[];
  approvedPrediction?: Prediction;
  overrideTitle?: string;
  status: "new" | "needs_review" | "confirmed" | "overridden";
  notes?: string;
  tags?: string[];
};
