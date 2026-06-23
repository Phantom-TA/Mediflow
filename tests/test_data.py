import os
import json
from datetime import time

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def load_json_file(filename):
    path = os.path.join(ROOT_DIR, "data", filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def test_departments_valid():
    depts = load_json_file("departments.json")
    assert len(depts) >= 15, "Should have at least 15 departments"
    ids = [d["id"] for d in depts]
    names = [d["name"] for d in depts]
    
    assert len(ids) == len(set(ids)), "Department IDs must be unique"
    assert len(names) == len(set(names)), "Department names must be unique"
    for d in depts:
        assert "id" in d and "name" in d and "description" in d
        assert len(d["id"]) > 0
        assert len(d["name"]) > 0

def test_doctors_valid():
    doctors = load_json_file("doctors.json")
    depts = load_json_file("departments.json")
    
    dept_names = {d["name"] for d in depts}
    
    assert len(doctors) >= 15, "Should have at least 15 doctors"
    
    seen_names = set()
    for doc in doctors:
        # Check critical fields
        assert "name" in doc and len(doc["name"]) > 0
        assert "specialty" in doc and len(doc["specialty"]) > 0
        assert "department" in doc and len(doc["department"]) > 0
        assert "qualifications" in doc and len(doc["qualifications"]) > 0
        assert "experience_years" in doc and doc["experience_years"] >= 0
        assert "designation" in doc and len(doc["designation"]) > 0
        assert "languages" in doc and isinstance(doc["languages"], list) and len(doc["languages"]) > 0
        assert "source_url" in doc and doc["source_url"].startswith("http")
        
        # Check department is valid
        assert doc["department"] in dept_names or doc["department"] == "Gynecology & Obstetrics", \
            f"Doctor {doc['name']} department '{doc['department']}' not in departments.json"
        
        # Check no duplicates within same specialty
        key = (doc["name"], doc["specialty"])
        assert key not in seen_names, f"Duplicate doctor in same specialty: {key}"
        seen_names.add(key)

def test_availability_valid():
    avail = load_json_file("availability.json")
    doctors = load_json_file("doctors.json")
    
    doc_names = {d["name"] for d in doctors}
    avail_doc_names = {item["doctor_name"] for item in avail}
    
    # Check that all doctors in availability list exist in doctors list
    for item in avail:
        assert item["doctor_name"] in doc_names, f"Doctor '{item['doctor_name']}' in availability not found in doctors.json"
        
        # Every doctor must have at least one availability window
        assert len(item["windows"]) > 0, f"Doctor '{item['doctor_name']}' has no availability windows"
        
        for win in item["windows"]:
            assert 0 <= win["day_of_week"] <= 6, f"Invalid day of week {win['day_of_week']}"
            assert win["slot_duration"] in (10, 15, 20, 30), f"Invalid slot duration {win['slot_duration']}"
            
            # Check time parsing and start < end
            start_h, start_m = map(int, win["start_time"].split(":"))
            end_h, end_m = map(int, win["end_time"].split(":"))
            
            start = time(start_h, start_m)
            end = time(end_h, end_m)
            
            assert start < end, f"Start time {win['start_time']} must be less than end time {win['end_time']}"

    # Check that EVERY doctor from doctors.json has at least one availability item
    for doc in doctors:
        assert doc["name"] in avail_doc_names, f"Doctor '{doc['name']}' from doctors.json has no entry in availability.json"
