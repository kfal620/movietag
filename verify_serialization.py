import sys
import os
import json

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.api.routes.frames import _serialize_frame
from app.models import Frame

def verify_serialization():
    # Mock a frame
    frame = Frame(
        id=1,
        file_path="test.jpg",
        analysis_log={"foo": "bar"}
    )
    
    serialized = _serialize_frame(frame)
    print("Serialized analysisLog:", serialized.get("analysisLog"))
    
    if serialized.get("analysisLog") == {"foo": "bar"}:
        print("SUCCESS: analysisLog correctly serialized")
    else:
        print("FAILED: analysisLog missing or incorrect")
        sys.exit(1)

if __name__ == "__main__":
    verify_serialization()
