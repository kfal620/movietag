import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.db import SessionLocal
from app.models import Frame
from sqlalchemy import func

def verify_fix():
    session = SessionLocal()
    try:
        print("Checking column type via reflection/query...")
        # Simple test: try a distinct count query which failed before
        try:
            count = session.query(Frame).distinct().count()
            print(f"SUCCESS: SELECT DISTINCT count query executed. Count: {count}")
        except Exception as e:
            print(f"FAILED: Query failed with error: {e}")
            sys.exit(1)
            
    finally:
        session.close()

if __name__ == "__main__":
    verify_fix()
