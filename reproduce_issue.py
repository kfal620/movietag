import sqlalchemy
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import scoped_session, sessionmaker, declarative_base

print(f"SQLAlchemy version: {sqlalchemy.__version__}")

Base = declarative_base()
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String)

# Use SQLite memory
engine = create_engine('sqlite:///:memory:')
Base.metadata.create_all(engine)

# Mimic app/db.py
SessionLocal = scoped_session(sessionmaker(bind=engine))

def internal_function():
    print("  [Inner] requesting session...")
    session = SessionLocal()
    print(f"  [Inner] session object: {session}")
    # Simulate DB work
    session.add(User(name="Inner"))
    session.commit()
    print("  [Inner] work done, calling remove()")
    # Mimic _cleanup_session / _session_scope logic
    SessionLocal.remove()
    print("  [Inner] session removed from registry")

def main():
    print("[Outer] requesting session...")
    db = SessionLocal()
    print(f"[Outer] session object: {db}")
    
    user = User(name="Outer")
    db.add(user)
    db.commit()
    db.refresh(user)
    print(f"[Outer] user created, bound to session: {user in db}")
    
    print("[Outer] Calling internal function...")
    internal_function()
    
    print("[Outer] Back in outer function.")
    # At this point, the session 'db' refers to has been closed/removed by inner function
    
    try:
        print("[Outer] Trying to refresh user...")
        # boolean check might not fail, but refresh definitely will if detached
        # accessing lazy attr would also fail
        db.refresh(user) 
        print("[Outer] Refresh SUCCESS (Unexpected)")
    except Exception as e:
        print(f"[Outer] Caught expected error: {e}")
        
    try:
        print("[Outer] Trying to access session...")
        # If db is a proxy, this might create a NEW session
        # But 'user' belongs to the OLD session
        if user not in db:
            print("[Outer] User is NOT in the current db session (Expected)")
        else:
            print("[Outer] User IS in the db session (Unexpected)")
            
    except Exception as e:
         print(f"[Outer] Error checking user in db: {e}")

if __name__ == "__main__":
    main()
