# Vision Pipeline System - Setup & Usage Guide

## Quick Start

### 1. Run Database Migration

The new `frame_embeddings` table must be created before using the multi-pipeline system.

**Option A: Using virtual environment** (recommended)
```bash
cd backend
source .venv/bin/activate  # or your venv path
alembic upgrade head
deactivate
```

**Option B: Using Docker/Docker Compose**
```bash
docker-compose exec backend alembic upgrade head
```

**Option C: Manual SQL** (if alembic unavailable)
```sql
CREATE TABLE frame_embeddings (
    id SERIAL PRIMARY KEY,
    frame_id INTEGER NOT NULL REFERENCES frames(id) ON DELETE CASCADE,
    pipeline_id VARCHAR(100) NOT NULL,
    embedding TEXT NOT NULL,
    model_version VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_frame_embedding_pipeline UNIQUE (frame_id, pipeline_id)
);

CREATE INDEX ix_frame_embeddings_frame_id ON frame_embeddings(frame_id);
CREATE INDEX ix_frame_embeddings_pipeline_id ON frame_embeddings(pipeline_id);
```

### 2. Verify Backend Setup

Start the backend and verify pipelines are registered:

```bash
cd backend
uvicorn app.main:app --reload
```

Then in another terminal:
```bash
curl http://localhost:8000/api/vision/pipelines
```

Expected output:
```json
{
  "pipelines": [
    {
      "id": "clip_vitb32",
      "name": "CLIP ViT-B/32 (Standard)",
      "model_id": "ViT-B-32",
      "input_resolution": 224,
      "device": "mps",  // or "cpu"
      "dtype": "float32",
      "version": "2.24.0",
      "loaded": false  // true after first use
    },
    {
      "id": "openclip_vitl14",
      "name": "OpenCLIP ViT-L/14 (Enhanced)",
      "model_id": "ViT-L-14",
      "input_resolution": 224,
      "device": "mps",
      "dtype": "float32",
      "version": "2.24.0",
      "loaded": false
    }
  ]
}
```

### 3. Test Frame Analysis

Analyze a frame with the enhanced pipeline:

```bash
# Replace YOUR_TOKEN with admin or moderator token
# Replace 1 with an actual frame ID from your database
curl -X POST http://localhost:8000/api/vision/analyze \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "frame_id": 1,
    "pipeline_id": "openclip_vitl14",
    "force": false
  }'
```

Expected response:
```json
{
  "status": "success",
  "frame_id": 1,
  "pipeline_id": "openclip_vitl14",
  "embedding": [0.123, 0.456, ...],  // 768-dim for ViT-L/14
  "embedding_dimension": 768,
  "attributes": [
    {
      "attribute": "time_of_day",
      "value": "day",
      "confidence": 0.92,
      "is_verified": false
    },
    // ... more attributes
  ],
  "cached": false,
  "embed_time": 0.45,
  "attribute_time": 0.12
}
```

### 4. Start Frontend

```bash
cd frontend
npm run dev
```

Visit http://localhost:3000 and:
1. Open Settings panel
2. Scroll to "Vision Pipelines" section
3. Verify both pipelines are listed
4. Click "Load / warm up models" if needed

---

## Configuration

### Environment Variables

Add to `backend/.env`:

```bash
# Standard CLIP (existing)
CLIP_MODEL_NAME=ViT-B-32
CLIP_PRETRAINED=openai

# Enhanced CLIP (new)
ENHANCED_CLIP_MODEL_NAME=ViT-L-14
ENHANCED_CLIP_PRETRAINED=laion2b_s32b_b82k
ENHANCED_CLIP_BATCH_SIZE=4
```

### Model Selection

**CLIP ViT-B/32** (Standard):
- Fast inference (~100ms on MPS)
- 512-dimensional embeddings
- Good for real-time analysis
- Lower memory usage (~350MB)

**OpenCLIP ViT-L/14** (Enhanced):
- Better accuracy (~5-10% improvement)
- 768-dimensional embeddings  
- Slower inference (~300ms on MPS)
- Higher memory usage (~900MB)

### Device Selection

The system automatically detects and uses:
1. **MPS** (Metal Performance Shaders) on Apple Silicon Macs
2. **CUDA** if NVIDIA GPU is available
3. **CPU** as fallback

Check logs for device selection:
```
INFO:app.services.vision_pipelines.clip_vitb32:Loaded CLIP ViT-B/32 pipeline: ViT-B-32 (openai) on mps
INFO:app.services.vision_pipelines.openclip_vitl14:Loaded OpenCLIP ViT-L/14 pipeline: ViT-L-14 (laion2b_s32b_b82k) on mps
```

---

## Usage Examples

### Python API

```python
from app.services.vision_pipelines import get_pipeline, list_pipelines
from app.services import vision_service
from app.db import get_db
from PIL import Image

# List available pipelines
for pipeline in list_pipelines():
    print(f"{pipeline.id}: {pipeline.name} (loaded={pipeline.loaded})")

# Get a specific pipeline
pipeline = get_pipeline("openclip_vitl14")

# Embed an image directly
image = Image.open("frame.jpg")
result = pipeline.embed_image(image)
print(f"Embedding dimension: {len(result.embedding)}")

# Score attributes
scores = pipeline.score_attributes(image=image)
for score in scores:
    print(f"{score.attribute}={score.value} ({score.confidence:.2f})")

# Full frame analysis with caching
session = next(get_db())
result = vision_service.analyze_frame(
    frame_id=123,
    pipeline_id="openclip_vitl14",
    force=False,  # use cache if available
    session=session
)
print(f"Cached: {result['cached']}")
print(f"Embedding dim: {result['embedding_dimension']}")
```

### Adding a New Pipeline

1. **Create pipeline class** in `backend/app/services/vision_pipelines/`:

```python
from .base import VisionPipeline, PipelineMetadata, EmbeddingResult, AttributeScore

class MyCustomPipeline(VisionPipeline):
    def get_metadata(self) -> PipelineMetadata:
        return PipelineMetadata(
            id="my_pipeline",
            name="My Custom Pipeline",
            model_id="custom-model-v1",
            input_resolution=384,
            device="cuda",
            dtype="float32",
            loaded=True,
        )
    
    def embed_image(self, image):
        # Your embedding logic here
        pass
    
    def score_attributes(self, image=None, embedding=None, session=None):
        # Your attribute scoring logic here
        pass
    
    def status(self):
        return {"loaded": True, "device": "cuda"}
```

2. **Register in `__init__.py`**:

```python
from .my_custom import MyCustomPipeline

def _auto_register_pipelines():
    # ... existing registrations ...
    
    try:
        custom = MyCustomPipeline()
        register_pipeline(custom)
    except Exception as e:
        logger.error("Failed to register custom pipeline: %s", e)
```

3. **Restart backend** - pipeline automatically available at `/api/vision/pipelines`

---

## Troubleshooting

### Models not loading

**Issue**: `"loaded": false` in pipeline status

**Solution**:
1. Check import errors in logs
2. Verify `open-clip-torch` is installed: `pip list | grep open-clip`
3. Try manual warmup: `curl -X POST http://localhost:8000/api/models/vision/warmup -H "Authorization: Bearer YOUR_TOKEN"`

### MPS not available

**Issue**: Pipeline shows `"device": "cpu"` on Mac

**Solutions**:
- Ensure macOS 12.3+ and Python 3.8+
- Check PyTorch MPS: `python3 -c "import torch; print(torch.backends.mps.is_available())"`
- Reinstall PyTorch with MPS support

### Embeddings not cached

**Issue**: `"cached": false` on every call

**Check**:
1. Database migration ran: `SELECT COUNT(*) FROM frame_embeddings;`
2. No errors in `store_frame_embedding()` logs
3. Pipeline ID is exactly `"clip_vitb32"` or `"openclip_vitl14"` (case-sensitive)

### Import errors

**Issue**: `ModuleNotFoundError: No module named 'app.services.vision_pipelines'`

**Solutions**:
1. Restart backend server to pick up new modules
2. Check `__init__.py` files exist in package directories
3. Verify Python path includes backend directory

---

## Performance Tips

### Batch Processing

For analyzing multiple frames, use the enhanced pipeline's batch method:

```python
from PIL import Image

pipeline = get_pipeline("openclip_vitl14")
images = [Image.open(f"frame_{i}.jpg") for i in range(10)]

# Process 4 at a time (configurable)
results = pipeline.embed_images_batch(images, batch_size=4)
```

### Caching Strategy

- First analysis: ~500ms (model load + inference)
- Cached analysis: ~5ms (database lookup)
- Force recompute only when needed (new model version, updated prototypes)

### Memory Management

Both models loaded simultaneously: ~1.3GB GPU memory

To reduce usage:
- Use only standard pipeline (set in localStorage)
- Lazy loading means enhanced model only loads when first used
- Models automatically unload when process restarts

---

## Next Steps

1. **Frontend integration**: Connect FrameEditModal to use selected pipeline
2. **Batch jobs**: Add Celery task for multi-frame enhanced analysis
3. **Trained heads**: Add linear classifier on top of embeddings
4. **More pipelines**: SigLIP, DINOv2, etc.

See `walkthrough.md` for complete implementation details.
