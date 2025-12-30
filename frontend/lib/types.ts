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
  isVerified?: boolean;
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

export type TmdbSearchResult = {
  tmdb_id: number;
  title: string;
  release_year?: number | null;
  overview?: string | null;
  poster_path?: string | null;
};

export type Frame = {
  id: number;
  movieId: number | null;
  movieTitle: string;
  filePath: string;
  storageUri?: string | null;
  signedUrl?: string | null;
  imageUrl: string;
  ingestSource?: string;
  metadataSource?: string | null;
  predictions: Prediction[];
  approvedPrediction?: Prediction;
  overrideTitle?: string;
  status: "needs_analyzing" | "analyzed" | "tmdb_only" | "confirmed";
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
  embeddingModel?: string | null;
  embeddingModelVersion?: string | null;
  analysisLog?: Record<string, any> | null;
  embeddings?: FrameEmbeddingInfo[];
};

export type VisionPipeline = {
  id: string;
  name: string;
  model_id: string;
  input_resolution: number;
  device: string;
  dtype: string;
  version?: string | null;
  loaded: boolean;
};

export type PipelinesResponse = {
  pipelines: VisionPipeline[];
};

export type AnalyzeFrameRequest = {
  frame_id: number;
  pipeline_id?: string;
  force?: boolean;
};

export type AnalyzeFrameResponse = {
  status: string;
  frame_id: number;
  pipeline_id: string;
  embedding: number[];
  embedding_dimension: number;
  attributes: SceneAttribute[];
  cached: boolean;
  embed_time?: number;
  attribute_time?: number;
};

export type FrameEmbeddingInfo = {
  id: number;
  frameId?: number;
  pipelineId: string;
  pipelineName?: string;
  dimension: number;
  modelVersion?: string | null;
  createdAt: string;
  userEdited?: boolean;
  isPipelineDefault?: boolean;
};

export type PrototypeInfo = {
  attribute: string;
  value: string;
  count: number;
  frameIds: number[];
  avgInfluence?: number;
};
