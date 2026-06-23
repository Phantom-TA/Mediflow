import os
import sys
import json

# Add the backend directory to Python path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(BACKEND_DIR, ".env"))

from app.config import get_settings  # noqa: E402
from app.database import create_engine, sessionmaker, Base  # noqa: E402
from app.models.clinic import Clinic  # noqa: E402
from app.models.doctor import Doctor  # noqa: E402
from app.models.availability import Availability  # noqa: E402
from app.models.slot import Slot  # noqa: E402
from app.models.appointment import Appointment  # noqa: E402

def seed_db():
    settings = get_settings()
    db_url = settings.effective_database_url
    print(f"Connecting to database: {db_url.split('@')[-1]}")
    
    engine = create_engine(db_url, echo=False)
    # Ensure all tables exist
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    
    try:
        # 1. Clean existing data in dependency order
        print("Cleaning up old database records...")
        session.query(Appointment).delete()
        session.query(Slot).delete()
        session.query(Availability).delete()
        session.query(Doctor).delete()
        session.query(Clinic).delete()
        session.commit()
        
        # 2. Insert Clinic
        print("Inserting Clinic...")
        clinic = Clinic(
            name="Apollo Hospital Bannerghatta Road",
            address="154/11, Opp. IIM-B, Bannerghatta Road",
            city="Bengaluru",
            state="Karnataka",
            phone="+91 80 2630 4050",
            website_url="https://www.apollohospitals.com/hospitals/bangalore/bannerghatta-road/",
            source_url="https://www.apollohospitals.com/hospitals/bangalore/bannerghatta-road/"
        )
        session.add(clinic)
        session.flush() # Populate clinic.id
        
        # 3. Load Doctors from JSON
        doctors_path = os.path.join(ROOT_DIR, "data", "doctors.json")
        print(f"Loading doctors from {doctors_path}...")
        with open(doctors_path, "r", encoding="utf-8") as f:
            doctors_data = json.load(f)
            
        doctor_map = {} # Keep name -> Doctor ORM mapping
        for doc_item in doctors_data:
            doc = Doctor(
                clinic_id=clinic.id,
                salutation=doc_item.get("salutation", "Dr."),
                name=doc_item["name"],
                specialty=doc_item["specialty"],
                department=doc_item["department"],
                qualifications=doc_item["qualifications"],
                experience_years=doc_item["experience_years"],
                designation=doc_item["designation"],
                languages=doc_item["languages"],
                source_url=doc_item["source_url"]
            )
            session.add(doc)
            session.flush()
            doctor_map[doc.name] = doc
            
        print(f"Successfully seeded {len(doctor_map)} doctors.")
        
        # 4. Load Availability from JSON
        avail_path = os.path.join(ROOT_DIR, "data", "availability.json")
        print(f"Loading availability windows from {avail_path}...")
        with open(avail_path, "r", encoding="utf-8") as f:
            avail_data = json.load(f)
            
        avail_count = 0
        for item in avail_data:
            doc_name = item["doctor_name"]
            if doc_name not in doctor_map:
                print(f"Warning: Doctor '{doc_name}' from availability.json not found in seeded doctors. Skipping.")
                continue
            
            doctor = doctor_map[doc_name]
            for win in item["windows"]:
                start_h, start_m = map(int, win["start_time"].split(":"))
                end_h, end_m = map(int, win["end_time"].split(":"))
                
                from datetime import time
                avail = Availability(
                    doctor_id=doctor.id,
                    day_of_week=win["day_of_week"],
                    start_time=time(start_h, start_m),
                    end_time=time(end_h, end_m),
                    slot_duration=win["slot_duration"],
                    source_url=doctor.source_url
                )
                session.add(avail)
                avail_count += 1
                
        session.commit()
        print(f"Successfully seeded {avail_count} availability windows!")
        
    except Exception as e:
        session.rollback()
        print(f"Seeding failed and transaction was rolled back: {e}")
        sys.exit(1)
    finally:
        session.close()

if __name__ == "__main__":
    seed_db()
