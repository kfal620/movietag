export type Prediction = {
  source: string;
  title: string;
  confidence: number;
  year?: number;
};

export type Frame = {
  id: number;
  movieId: number;
  movieTitle: string;
  imageUrl: string;
  ingestSource?: string;
  predictions: Prediction[];
  approvedPrediction?: Prediction;
  overrideTitle?: string;
  status: "pending" | "new" | "needs_review" | "confirmed" | "overridden" | "tagged" | "embedded" | "scene_annotated" | "actors_detected";
  notes?: string;
  tags?: string[];
  sceneAttributes?: { attribute: string; value: string; confidence?: number }[];
  actors?: { castMemberId: number | null; confidence?: number }[];
};
