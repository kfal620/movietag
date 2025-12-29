"""Remove duplicate frames based on storage_uri and file_path.

This script identifies duplicate frames and keeps only the best one based on:
1. Status priority: analyzed > tmdb_only > confirmed > needs_analyzing
2. If same status, keep the older frame (earlier created_at)
"""

from app.db import SessionLocal
from app.models import Frame
from sqlalchemy import func

STATUS_PRIORITY = {
    "confirmed": 4,
    "analyzed": 3,
    "tmdb_only": 2,
    "needs_analyzing": 1,
}


def get_frame_score(frame: Frame) -> tuple:
    """Return a score tuple for sorting (higher is better to keep)."""
    status_score = STATUS_PRIORITY.get(frame.status, 0)
    # Negative timestamp so older is better
    return (status_score, -frame.created_at.timestamp())


def remove_duplicates():
    """Remove duplicate frames, keeping the best one."""
    session = SessionLocal()
    
    try:
        # Find duplicates by storage_uri
        print("Finding duplicates by storage_uri...")
        storage_duplicates = (
            session.query(Frame.storage_uri, func.count(Frame.id))
            .filter(Frame.storage_uri.isnot(None))
            .group_by(Frame.storage_uri)
            .having(func.count(Frame.id) > 1)
            .all()
        )
        
        # Find duplicates by file_path
        print("Finding duplicates by file_path...")
        path_duplicates = (
            session.query(Frame.file_path, func.count(Frame.id))
            .filter(Frame.file_path.isnot(None))
            .group_by(Frame.file_path)
            .having(func.count(Frame.id) > 1)
            .all()
        )
        
        total_deleted = 0
        
        # Process storage_uri duplicates
        for storage_uri, count in storage_duplicates:
            frames = (
                session.query(Frame)
                .filter(Frame.storage_uri == storage_uri)
                .all()
            )
            
            # Sort by score (best first)
            frames_sorted = sorted(frames, key=get_frame_score, reverse=True)
            keep = frames_sorted[0]
            to_delete = frames_sorted[1:]
            
            print(f"\nStorage URI: {storage_uri}")
            print(f"  Keeping: ID {keep.id} (status={keep.status}, created={keep.created_at})")
            
            for frame in to_delete:
                print(f"  Deleting: ID {frame.id} (status={frame.status}, created={frame.created_at})")
                session.delete(frame)
                total_deleted += 1
        
        # Process file_path duplicates (only if not already handled by storage_uri)
        processed_ids = set()
        for file_path, count in path_duplicates:
            frames = (
                session.query(Frame)
                .filter(Frame.file_path == file_path)
                .all()
            )
            
            # Skip if already processed via storage_uri
            if all(f.id in processed_ids for f in frames):
                continue
            
            # Filter out already deleted frames
            frames = [f for f in frames if f in session]
            if len(frames) <= 1:
                continue
            
            frames_sorted = sorted(frames, key=get_frame_score, reverse=True)
            keep = frames_sorted[0]
            to_delete = frames_sorted[1:]
            
            print(f"\nFile path: {file_path}")
            print(f"  Keeping: ID {keep.id} (status={keep.status}, created={keep.created_at})")
            
            for frame in to_delete:
                print(f"  Deleting: ID {frame.id} (status={frame.status}, created={frame.created_at})")
                session.delete(frame)
                total_deleted += 1
            
            processed_ids.update(f.id for f in frames)
        
        print(f"\n\nTotal frames deleted: {total_deleted}")
        
        if total_deleted > 0:
            confirm = input("\nCommit these changes? (yes/no): ")
            if confirm.lower() == "yes":
                session.commit()
                print("✅ Changes committed!")
            else:
                session.rollback()
                print("❌ Changes rolled back")
        else:
            print("No duplicates found!")
    
    finally:
        session.close()


if __name__ == "__main__":
    remove_duplicates()
