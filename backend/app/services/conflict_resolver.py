import difflib
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session, joinedload
from app.models.doctor import Doctor
from app.models.slot import Slot

# Common patient terms mapped to clinical specialties/departments present in Apollo dataset
SPECIALTY_ALIASES = {
    # Cardiology
    "heart": ["Cardiology", "Interventional Cardiology"],
    "cardio": ["Cardiology", "Interventional Cardiology"],
    "cardiology": ["Cardiology", "Interventional Cardiology"],
    "cardiologist": ["Cardiology", "Interventional Cardiology"],
    
    # Orthopedics
    "bone": ["Orthopedics", "Joint Replacement & Orthopedics", "Orthopedics & Joint Replacement"],
    "fracture": ["Orthopedics", "Joint Replacement & Orthopedics", "Orthopedics & Joint Replacement"],
    "ortho": ["Orthopedics", "Joint Replacement & Orthopedics", "Orthopedics & Joint Replacement"],
    "orthopedics": ["Orthopedics", "Joint Replacement & Orthopedics", "Orthopedics & Joint Replacement"],
    "orthopaedic": ["Orthopedics", "Joint Replacement & Orthopedics", "Orthopedics & Joint Replacement"],
    "orthopaedics": ["Orthopedics", "Joint Replacement & Orthopedics", "Orthopedics & Joint Replacement"],
    "orthopedist": ["Orthopedics", "Joint Replacement & Orthopedics", "Orthopedics & Joint Replacement"],
    "joint": ["Orthopedics", "Joint Replacement & Orthopedics", "Orthopedics & Joint Replacement"],
    "knee": ["Orthopedics", "Joint Replacement & Orthopedics", "Orthopedics & Joint Replacement"],

    # Gastroenterology
    "stomach": ["Gastroenterology", "Gastroenterology & Hepatology"],
    "gastric": ["Gastroenterology", "Gastroenterology & Hepatology"],
    "gastro": ["Gastroenterology", "Gastroenterology & Hepatology"],
    "gastroenterology": ["Gastroenterology", "Gastroenterology & Hepatology"],
    "digestive": ["Gastroenterology", "Gastroenterology & Hepatology"],
    "liver": ["Gastroenterology", "Gastroenterology & Hepatology"],
    "hepatology": ["Gastroenterology", "Gastroenterology & Hepatology"],
    "hepatologist": ["Gastroenterology", "Gastroenterology & Hepatology"],

    # Pulmonology
    "lung": ["Pulmonology", "Pulmonology & Respiratory Medicine"],
    "breathing": ["Pulmonology", "Pulmonology & Respiratory Medicine"],
    "chest": ["Pulmonology", "Pulmonology & Respiratory Medicine"],
    "pulmono": ["Pulmonology", "Pulmonology & Respiratory Medicine"],
    "pulmonology": ["Pulmonology", "Pulmonology & Respiratory Medicine"],
    "asthma": ["Pulmonology", "Pulmonology & Respiratory Medicine"],
    "respiratory": ["Pulmonology", "Pulmonology & Respiratory Medicine"],

    # Dermatology
    "skin": ["Dermatology"],
    "hair": ["Dermatology"],
    "nail": ["Dermatology"],
    "derma": ["Dermatology"],
    "dermatology": ["Dermatology"],
    "dermatologist": ["Dermatology"],
    "allergy": ["Dermatology", "Pulmonology & Respiratory Medicine"],

    # Neurology
    "brain": ["Neurology", "Neurosurgery (Brain & Spine)"],
    "nerve": ["Neurology", "Neurosurgery (Brain & Spine)"],
    "neurology": ["Neurology", "Neurosurgery (Brain & Spine)"],
    "neurologist": ["Neurology", "Neurosurgery (Brain & Spine)"],
    "neuro": ["Neurology", "Neurosurgery (Brain & Spine)"],
    "stroke": ["Neurology"],

    # Pediatrics
    "child": ["Pediatrics", "Pediatrics & Neonatology"],
    "kid": ["Pediatrics", "Pediatrics & Neonatology"],
    "baby": ["Pediatrics", "Pediatrics & Neonatology"],
    "pediatric": ["Pediatrics", "Pediatrics & Neonatology"],
    "pediatrics": ["Pediatrics", "Pediatrics & Neonatology"],
    "pediatrician": ["Pediatrics", "Pediatrics & Neonatology"],
    "neonatology": ["Pediatrics & Neonatology"],

    # Gynecology
    "women": ["Gynecology & Obstetrics"],
    "female": ["Gynecology & Obstetrics"],
    "pregnancy": ["Gynecology & Obstetrics"],
    "pregnant": ["Gynecology & Obstetrics"],
    "gynaecologist": ["Gynecology & Obstetrics"],
    "gynecologist": ["Gynecology & Obstetrics"],
    "gynaecology": ["Gynecology & Obstetrics"],
    "gynecology": ["Gynecology & Obstetrics"],
    "obstetrics": ["Gynecology & Obstetrics"],
    "obgyn": ["Gynecology & Obstetrics"],
    "delivery": ["Gynecology & Obstetrics"],

    # ENT
    "ear": ["ENT (Ear, Nose & Throat)", "ENT (Ear, Nose, Throat)"],
    "nose": ["ENT (Ear, Nose & Throat)", "ENT (Ear, Nose, Throat)"],
    "throat": ["ENT (Ear, Nose & Throat)", "ENT (Ear, Nose, Throat)"],
    "ent": ["ENT (Ear, Nose & Throat)", "ENT (Ear, Nose, Throat)"],

    # Nephrology
    "kidney": ["Nephrology"],
    "renal": ["Nephrology"],
    "nephrology": ["Nephrology"],
    "dialysis": ["Nephrology"],

    # Urology
    "urine": ["Urology"],
    "urinary": ["Urology"],
    "prostate": ["Urology"],
    "urology": ["Urology"],

    # Oncology
    "cancer": ["Oncology"],
    "tumor": ["Oncology"],
    "oncology": ["Oncology"],
    "chemo": ["Oncology"],

    # General Surgery
    "surgery": ["General Surgery"],
    "surgeon": ["General Surgery"],
    "surgical": ["General Surgery"],

    # Endocrinology
    "diabetes": ["Endocrinology"],
    "hormone": ["Endocrinology"],
    "thyroid": ["Endocrinology"],
    "endocrinology": ["Endocrinology"],

    # Rheumatology
    "arthritis": ["Rheumatology"],
    "joint pain": ["Rheumatology", "Orthopedics"],
    "rheumatology": ["Rheumatology"],
    "gout": ["Rheumatology"],
}


def resolve_specialties_and_departments(query: str, db: Session) -> list[str]:
    """
    Resolves a medical specialty or query term to exact database specialties and departments.
    """
    if not query:
        return []

    q = query.strip().lower()

    # Get all active specialties and departments from Doctor model in DB
    all_specs_depts = set()
    for row in db.query(Doctor.specialty, Doctor.department).filter(Doctor.is_active.is_(True)).all():
        all_specs_depts.add(row.specialty)
        all_specs_depts.add(row.department)

    all_specs_depts_list = list(all_specs_depts)
    matched = set()

    # 1. Match against known aliases
    for alias_key, mapped_specs in SPECIALTY_ALIASES.items():
        if alias_key in q or q in alias_key:
            for s in mapped_specs:
                # Double-check that these exist in the DB (case-insensitive search)
                for db_val in all_specs_depts_list:
                    if s.lower() == db_val.lower() or s.lower() in db_val.lower() or db_val.lower() in s.lower():
                        matched.add(db_val)

    # 2. Substring matching on database specialties
    for db_val in all_specs_depts_list:
        db_val_lower = db_val.lower()
        if db_val_lower in q or q in db_val_lower:
            matched.add(db_val)

    # 3. Fuzzy matches if nothing found yet
    if not matched:
        # Match against aliases keys
        close_keys = difflib.get_close_matches(q, list(SPECIALTY_ALIASES.keys()), n=2, cutoff=0.7)
        for key in close_keys:
            for s in SPECIALTY_ALIASES[key]:
                for db_val in all_specs_depts_list:
                    if s.lower() == db_val.lower():
                        matched.add(db_val)

        # Match against DB values
        close_db_vals = difflib.get_close_matches(q, all_specs_depts_list, n=2, cutoff=0.7)
        for val in close_db_vals:
            matched.add(val)

    return list(matched)


def compute_alternative_slots(
    db: Session,
    specialty_query: str,
    preferred_doctor_id: str | None,
    preferred_date: datetime.date,
    preferred_time: str | None,
    max_results: int = 5,
) -> list[tuple[float, Slot, str]]:
    """
    Computes and ranks alternative slots based on user preference and heuristics:
      - Same doctor: 40%
      - Same specialty: 20%
      - Date proximity: 20%
      - Time proximity: 20%
    """
    ist_tz = ZoneInfo("Asia/Kolkata")
    now_utc = datetime.now(timezone.utc)

    # Resolve target specialties
    resolved_specs = resolve_specialties_and_departments(specialty_query, db)
    if not resolved_specs:
        # Fallback to direct text if no alias resolves
        resolved_specs = [specialty_query]

    # Query matching doctors
    doctors = db.query(Doctor).filter(
        (Doctor.specialty.in_(resolved_specs) | Doctor.department.in_(resolved_specs)),
        Doctor.is_active.is_(True)
    ).all()

    if not doctors and specialty_query:
        # Broaden match to check if any doctor specialty contains the text substring
        doctors = db.query(Doctor).filter(
            Doctor.is_active.is_(True),
            Doctor.specialty.ilike(f"%{specialty_query}%") | Doctor.department.ilike(f"%{specialty_query}%")
        ).all()

    if not doctors:
        return []

    doctor_ids = [doc.id for doc in doctors]
    {doc.id: doc for doc in doctors}

    # Query all available slots in next 14 days
    slots = (
        db.query(Slot)
        .options(joinedload(Slot.doctor))
        .filter(
            Slot.doctor_id.in_(doctor_ids),
            Slot.is_available.is_(True),
            Slot.slot_start >= now_utc,
            Slot.slot_start <= now_utc + timedelta(days=14),
        )
        .all()
    )

    # Parse preferred time
    preferred_min = None
    if preferred_time:
        try:
            h, m = map(int, preferred_time.split(":"))
            preferred_min = h * 60 + m
        except Exception:
            pass

    scored_slots = []
    for s in slots:
        score = 0.0

        # 1. Same doctor bonus (40%)
        is_same_doctor = preferred_doctor_id and s.doctor_id == preferred_doctor_id
        if is_same_doctor:
            score += 0.40

        # 2. Same specialty bonus (20%) - all queried slots have this
        score += 0.20

        s_ist = s.slot_start.astimezone(ist_tz)

        # 3. Date proximity (20%)
        days_diff = abs((s_ist.date() - preferred_date).days)
        score += 0.20 * max(0.0, 1.0 - (days_diff / 14.0))

        # 4. Time proximity (20%)
        if preferred_min is not None:
            slot_min = s_ist.hour * 60 + s_ist.minute
            min_diff = abs(slot_min - preferred_min)
            score += 0.20 * max(0.0, 1.0 - (min_diff / 720.0))  # 12h range normalization
        else:
            score += 0.20

        # Determine readable reason
        if is_same_doctor:
            reason = "Same doctor, closest available slot"
        else:
            reason = "Same specialty, closest available slot"

        scored_slots.append((score, s, reason))

    # Sort: highest score first, then earliest start time
    scored_slots.sort(key=lambda x: (-x[0], x[1].slot_start))

    return scored_slots[:max_results]
