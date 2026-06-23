import os
import sys

# Add the backend directory to Python path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(BACKEND_DIR, ".env"))

from app.config import get_settings  # noqa: E402
from app.database import create_engine, sessionmaker  # noqa: E402
from app.services.slot_engine import generate_all_slots  # noqa: E402

def main():
    settings = get_settings()
    db_url = settings.effective_database_url
    days = settings.slot_generation_days
    
    print(f"Generating slots for all doctors over the next {days} days...")
    print(f"Target DB: {db_url.split('@')[-1]}")
    
    engine = create_engine(db_url, echo=False)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    
    try:
        count = generate_all_slots(session, days=days)
        print(f"Slot generation complete. {count} new slots generated & saved!")
    except Exception as e:
        session.rollback()
        print(f"Failed to generate slots: {e}")
        sys.exit(1)
    finally:
        session.close()

if __name__ == "__main__":
    main()
