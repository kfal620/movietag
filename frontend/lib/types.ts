export type Prediction = {
  source: string;
  title: string;
  confidence: number;
  year?: number;
};

export type Tag = {
  id?: number;
  name: string;
  confidence?: number;
};

export type SceneAttribute = {
  id?: number;
  attribute: string;
  value: string;
  confidence?: number;
};

export type ActorDetection = {
  id?: number;
  castMemberId: number | null;
  castMemberName?: string | null;
  confidence?: number;
  faceIndex?: number | null;
  bbox?: number[] | null;
   clusterLabel?: string | null;
   trackStatus?: string | null;
   emotion?: string | null;
   poseYaw?: number | null;
   posePitch?: number | null;
   poseRoll?: number | null;
};

export type Frame = {
  id: number;
  movieId: number | null;
  movieTitle: string;
  filePath: string;
  storageUri?: string | null;
  signedUrl?: string | null;
  predictedMovieId?: number | null;
  predictedMovieTitle?: string | null;
  imageUrl: string;
  ingestSource?: string;
  metadataSource?: string | null;
  predictions: Prediction[];
  approvedPrediction?: Prediction;
  overrideTitle?: string;
  status: "pending" | "new" | "needs_review" | "confirmed" | "overridden" | "tagged" | "embedded" | "scene_annotated" | "actors_detected";
  matchConfidence?: number | null;
  predictedTimestamp?: string | null;
  predictedShotId?: string | null;
  shotTimestamp?: string | null;
  sceneSummary?: string | null;
  notes?: string;
  tags?: Tag[];
  sceneAttributes?: SceneAttribute[];
  actors?: ActorDetection[];
  capturedAt?: string | null;
};
