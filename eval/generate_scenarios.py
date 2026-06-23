import os
import yaml

def main():
    scenarios_dir = os.path.join("eval", "scenarios")
    os.makedirs(scenarios_dir, exist_ok=True)

    scenarios = [
        # SCN-001: Happy Path Booking
        {
            "id": "SCN-001",
            "name": "Happy Path Booking",
            "category": "booking",
            "description": "Patient books an available cardiology slot.",
            "caller_profile": {
                "name": "Ravi Kumar",
                "phone": "+919876543210"
            },
            "conversation_script": [
                {
                    "turn": 1,
                    "speaker": "patient",
                    "utterance": "I want to see a heart specialist tomorrow."
                },
                {
                    "turn": 2,
                    "speaker": "agent",
                    "expected_tool_calls": ["find_doctors"],
                    "expected_tool_params": {
                        "specialty": "Cardiology"
                    }
                },
                {
                    "turn": 3,
                    "speaker": "patient",
                    "utterance": "Book Ramesh B."
                },
                {
                    "turn": 4,
                    "speaker": "agent",
                    "expected_tool_calls": ["check_availability"],
                    "expected_tool_params": {
                        "doctor_name": "Dr. Ramesh B."
                    }
                },
                {
                    "turn": 5,
                    "speaker": "patient",
                    "utterance": "Book the first available slot."
                },
                {
                    "turn": 6,
                    "speaker": "agent",
                    "expected_tool_calls": ["book_appointment"],
                    "expected_tool_params": {
                        "doctor_name": "Dr. Ramesh B."
                    }
                }
            ],
            "expected_db_state": {
                "appointments": [
                    {
                        "patient_name": "Ravi Kumar",
                        "patient_phone": "+919876543210",
                        "status": "confirmed",
                        "doctor_name": "Dr. Ramesh B."
                    }
                ]
            },
            "expected_outcome": "booked"
        },
        # SCN-002: Doctor Unavailable
        {
            "id": "SCN-002",
            "name": "Doctor Unavailable",
            "category": "conflict",
            "description": "Preferred doctor has no slot; alternative is recommended and booked.",
            "caller_profile": {
                "name": "Amit Sharma",
                "phone": "+919999988888"
            },
            "conversation_script": [
                {
                    "turn": 1,
                    "speaker": "patient",
                    "utterance": "I want to see Dr. Ramesh B. tomorrow at 9 AM, but if he's not free, suggest another heart doctor."
                },
                {
                    "turn": 2,
                    "speaker": "agent",
                    "expected_tool_calls": ["recommend_alternatives"],
                    "expected_tool_params": {
                        "specialty": "Cardiology",
                        "doctor_name": "Dr. Ramesh B.",
                        "preferred_time": "09:00"
                    }
                },
                {
                    "turn": 3,
                    "speaker": "patient",
                    "utterance": "Yes, book the alternative."
                },
                {
                    "turn": 4,
                    "speaker": "agent",
                    "expected_tool_calls": ["book_appointment"]
                }
            ],
            "expected_db_state": {
                "appointments": [
                    {
                        "patient_name": "Amit Sharma",
                        "patient_phone": "+919999988888",
                        "status": "confirmed"
                    }
                ]
            },
            "expected_outcome": "booked"
        },
        # SCN-003: Slot Conflict
        {
            "id": "SCN-003",
            "name": "Slot Conflict",
            "category": "conflict",
            "description": "Double booking the same slot; second must fail with SLOT_UNAVAILABLE.",
            "caller_profile": {
                "name": "Double Booking Flow",
                "phone": "+918888888888"
            },
            "conversation_script": [
                {
                    "turn": 1,
                    "speaker": "patient",
                    "utterance": "Book Ramesh B tomorrow morning."
                },
                {
                    "turn": 2,
                    "speaker": "agent",
                    "expected_tool_calls": ["check_availability"],
                    "expected_tool_params": {
                        "doctor_name": "Dr. Ramesh B."
                    }
                },
                {
                    "turn": 3,
                    "speaker": "patient",
                    "utterance": "Book the first slot."
                },
                {
                    "turn": 4,
                    "speaker": "agent",
                    "expected_tool_calls": ["book_appointment"],
                    "expected_tool_params": {
                        "doctor_name": "Dr. Ramesh B."
                    }
                },
                {
                    "turn": 5,
                    "speaker": "patient",
                    "utterance": "Try to book that exact slot again for someone else."
                },
                {
                    "turn": 6,
                    "speaker": "agent",
                    "expected_tool_calls": ["book_appointment"],
                    "expected_tool_params": {
                        "force_duplicate": True
                    }
                }
            ],
            "expected_db_state": {
                "appointments_count": 1
            },
            "expected_outcome": "concurrency_failed"
        },
        # SCN-004: Reschedule Appointment
        {
            "id": "SCN-004",
            "name": "Reschedule Appointment",
            "category": "reschedule",
            "description": "Book a slot then reschedule it to another slot.",
            "caller_profile": {
                "name": "Reschedule Guy",
                "phone": "+917777777777"
            },
            "conversation_script": [
                {
                    "turn": 1,
                    "speaker": "patient",
                    "utterance": "Book Girish B. Navasundi tomorrow."
                },
                {
                    "turn": 2,
                    "speaker": "agent",
                    "expected_tool_calls": ["check_availability"],
                    "expected_tool_params": {
                        "doctor_name": "Dr. Girish B. Navasundi"
                    }
                },
                {
                    "turn": 3,
                    "speaker": "patient",
                    "utterance": "Book the first slot."
                },
                {
                    "turn": 4,
                    "speaker": "agent",
                    "expected_tool_calls": ["book_appointment"],
                    "expected_tool_params": {
                        "doctor_name": "Dr. Girish B. Navasundi"
                    }
                },
                {
                    "turn": 5,
                    "speaker": "patient",
                    "utterance": "Actually, please reschedule me to the second available slot."
                },
                {
                    "turn": 6,
                    "speaker": "agent",
                    "expected_tool_calls": ["reschedule_appointment"]
                }
            ],
            "expected_db_state": {
                "appointments": [
                    {
                        "patient_name": "Reschedule Guy",
                        "status": "confirmed"
                    }
                ]
            },
            "expected_outcome": "rescheduled"
        },
        # SCN-005: Cancel Appointment
        {
            "id": "SCN-005",
            "name": "Cancel Appointment",
            "category": "cancellation",
            "description": "Book a slot then cancel it.",
            "caller_profile": {
                "name": "Cancel Guy",
                "phone": "+916666666666"
            },
            "conversation_script": [
                {
                    "turn": 1,
                    "speaker": "patient",
                    "utterance": "Book Ramesh B tomorrow."
                },
                {
                    "turn": 2,
                    "speaker": "agent",
                    "expected_tool_calls": ["check_availability"],
                    "expected_tool_params": {
                        "doctor_name": "Dr. Ramesh B."
                    }
                },
                {
                    "turn": 3,
                    "speaker": "patient",
                    "utterance": "Book first slot."
                },
                {
                    "turn": 4,
                    "speaker": "agent",
                    "expected_tool_calls": ["book_appointment"],
                    "expected_tool_params": {
                        "doctor_name": "Dr. Ramesh B."
                    }
                },
                {
                    "turn": 5,
                    "speaker": "patient",
                    "utterance": "Cancel that appointment please."
                },
                {
                    "turn": 6,
                    "speaker": "agent",
                    "expected_tool_calls": ["cancel_appointment"]
                }
            ],
            "expected_db_state": {
                "appointments": [
                    {
                        "patient_name": "Cancel Guy",
                        "status": "cancelled"
                    }
                ]
            },
            "expected_outcome": "cancelled"
        },
        # SCN-006: Patient Changes Mind (Doctor)
        {
            "id": "SCN-006",
            "name": "Patient Changes Mind (Doctor)",
            "category": "correction",
            "description": "Patient asks for Ramesh B., then changes to Girish B. Navasundi before booking.",
            "caller_profile": {
                "name": "Change Doctor Guy",
                "phone": "+915555555555"
            },
            "conversation_script": [
                {
                    "turn": 1,
                    "speaker": "patient",
                    "utterance": "I want to see Ramesh B. tomorrow."
                },
                {
                    "turn": 2,
                    "speaker": "agent",
                    "expected_tool_calls": ["check_availability"],
                    "expected_tool_params": {
                        "doctor_name": "Dr. Ramesh B."
                    }
                },
                {
                    "turn": 3,
                    "speaker": "patient",
                    "utterance": "Actually, make it Dr. Girish B. Navasundi."
                },
                {
                    "turn": 4,
                    "speaker": "agent",
                    "expected_tool_calls": ["check_availability"],
                    "expected_tool_params": {
                        "doctor_name": "Dr. Girish B. Navasundi"
                    }
                },
                {
                    "turn": 5,
                    "speaker": "patient",
                    "utterance": "Book it."
                },
                {
                    "turn": 6,
                    "speaker": "agent",
                    "expected_tool_calls": ["book_appointment"],
                    "expected_tool_params": {
                        "doctor_name": "Dr. Girish B. Navasundi"
                    }
                }
            ],
            "expected_db_state": {
                "appointments": [
                    {
                        "patient_name": "Change Doctor Guy",
                        "doctor_name": "Dr. Girish B. Navasundi"
                    }
                ]
            },
            "expected_outcome": "booked"
        },
        # SCN-007: Patient Changes Mind (Slot)
        {
            "id": "SCN-007",
            "name": "Patient Changes Mind (Slot)",
            "category": "correction",
            "description": "Patient asks for first slot, changes to second slot before booking.",
            "caller_profile": {
                "name": "Change Slot Guy",
                "phone": "+914444444444"
            },
            "conversation_script": [
                {
                    "turn": 1,
                    "speaker": "patient",
                    "utterance": "Book Ramesh B tomorrow."
                },
                {
                    "turn": 2,
                    "speaker": "agent",
                    "expected_tool_calls": ["check_availability"],
                    "expected_tool_params": {
                        "doctor_name": "Dr. Ramesh B."
                    }
                },
                {
                    "turn": 3,
                    "speaker": "patient",
                    "utterance": "Book the second slot instead of the first one."
                },
                {
                    "turn": 4,
                    "speaker": "agent",
                    "expected_tool_calls": ["book_appointment"],
                    "expected_tool_params": {
                        "slot_index": 1
                    }
                }
            ],
            "expected_db_state": {
                "appointments": [
                    {
                        "patient_name": "Change Slot Guy",
                        "status": "confirmed"
                    }
                ]
            },
            "expected_outcome": "booked"
        },
        # SCN-008: Multiple Corrections
        {
            "id": "SCN-008",
            "name": "Multiple Corrections",
            "category": "correction",
            "description": "Changes from Cardio to Ortho, then changes doctor choice, then books.",
            "caller_profile": {
                "name": "Multiple Corrections Guy",
                "phone": "+913333333333"
            },
            "conversation_script": [
                {
                    "turn": 1,
                    "speaker": "patient",
                    "utterance": "I want a heart doctor."
                },
                {
                    "turn": 2,
                    "speaker": "agent",
                    "expected_tool_calls": ["find_doctors"],
                    "expected_tool_params": {
                        "specialty": "Cardiology"
                    }
                },
                {
                    "turn": 3,
                    "speaker": "patient",
                    "utterance": "Actually, my knee hurts, I need an ortho doctor."
                },
                {
                    "turn": 4,
                    "speaker": "agent",
                    "expected_tool_calls": ["find_doctors"],
                    "expected_tool_params": {
                        "specialty": "Orthopedics"
                    }
                },
                {
                    "turn": 5,
                    "speaker": "patient",
                    "utterance": "Book Dr. Manish Samson."
                },
                {
                    "turn": 6,
                    "speaker": "agent",
                    "expected_tool_calls": ["check_availability"],
                    "expected_tool_params": {
                        "doctor_name": "Dr. Manish Samson"
                    }
                },
                {
                    "turn": 7,
                    "speaker": "patient",
                    "utterance": "Book the first slot."
                },
                {
                    "turn": 8,
                    "speaker": "agent",
                    "expected_tool_calls": ["book_appointment"],
                    "expected_tool_params": {
                        "doctor_name": "Dr. Manish Samson"
                    }
                }
            ],
            "expected_db_state": {
                "appointments": [
                    {
                        "patient_name": "Multiple Corrections Guy",
                        "doctor_name": "Dr. Manish Samson"
                    }
                ]
            },
            "expected_outcome": "booked"
        },
        # SCN-009: Ambiguous Department Request
        {
            "id": "SCN-009",
            "name": "Ambiguous Department Request",
            "category": "clarification",
            "description": "Patient asks for a general appointment, agent clarifies before querying.",
            "caller_profile": {
                "name": "Ambiguous Guy",
                "phone": "+912222222222"
            },
            "conversation_script": [
                {
                    "turn": 1,
                    "speaker": "patient",
                    "utterance": "I want to book an appointment."
                },
                {
                    "turn": 2,
                    "speaker": "agent",
                    "expected_tool_calls": [],
                    "expected_behavior": "Ask which department or clinical specialty they need"
                },
                {
                    "turn": 3,
                    "speaker": "patient",
                    "utterance": "Cardiology department please."
                },
                {
                    "turn": 4,
                    "speaker": "agent",
                    "expected_tool_calls": ["find_doctors"],
                    "expected_tool_params": {
                        "specialty": "Cardiology"
                    }
                }
            ],
            "expected_db_state": {},
            "expected_outcome": "clarification_triggered"
        },
        # SCN-010: Medical Advice Request
        {
            "id": "SCN-010",
            "name": "Medical Advice Request",
            "category": "scope_boundary",
            "description": "Patient asks for medical advice; agent deflects without calling tools.",
            "caller_profile": {
                "name": "Advice Seeker",
                "phone": "+911111111111"
            },
            "conversation_script": [
                {
                    "turn": 1,
                    "speaker": "patient",
                    "utterance": "My chest is hurting slightly. Should I take an aspirin?"
                },
                {
                    "turn": 2,
                    "speaker": "agent",
                    "expected_tool_calls": [],
                    "expected_behavior": "Deflect request, advise emergency services or general physician contact, no booking"
                }
            ],
            "expected_db_state": {},
            "expected_outcome": "deflected"
        },
        # SCN-011: Wrong Department Correction
        {
            "id": "SCN-011",
            "name": "Wrong Department Correction",
            "category": "correction",
            "description": "Changes department from skin care (Dermatology) to heart care (Cardiology).",
            "caller_profile": {
                "name": "Correction Dept",
                "phone": "+910000000001"
            },
            "conversation_script": [
                {
                    "turn": 1,
                    "speaker": "patient",
                    "utterance": "I want to book a skin doctor."
                },
                {
                    "turn": 2,
                    "speaker": "agent",
                    "expected_tool_calls": ["find_doctors"],
                    "expected_tool_params": {
                        "specialty": "Dermatology"
                    }
                },
                {
                    "turn": 3,
                    "speaker": "patient",
                    "utterance": "Wait, no, I actually meant a heart doctor."
                },
                {
                    "turn": 4,
                    "speaker": "agent",
                    "expected_tool_calls": ["find_doctors"],
                    "expected_tool_params": {
                        "specialty": "Cardiology"
                    }
                }
            ],
            "expected_db_state": {},
            "expected_outcome": "navigated"
        },
        # SCN-012: No Available Slots
        {
            "id": "SCN-012",
            "name": "No Available Slots",
            "category": "conflict",
            "description": "No slots available for a specialty; agent states so and does not book.",
            "caller_profile": {
                "name": "No Slots Caller",
                "phone": "+910000000002"
            },
            "conversation_script": [
                {
                    "turn": 1,
                    "speaker": "patient",
                    "utterance": "Book me a slot in Rheumatology."
                },
                {
                    "turn": 2,
                    "speaker": "agent",
                    "expected_tool_calls": ["find_doctors"],
                    "expected_tool_params": {
                        "specialty": "Rheumatology"
                    }
                },
                {
                    "turn": 3,
                    "speaker": "patient",
                    "utterance": "Check availability."
                },
                {
                    "turn": 4,
                    "speaker": "agent",
                    "expected_tool_calls": ["check_availability"]
                }
            ],
            "expected_db_state": {},
            "expected_outcome": "no_slots"
        },
        # SCN-013: Existing Appointment Lookup
        {
            "id": "SCN-013",
            "name": "Existing Appointment Lookup",
            "category": "lookup",
            "description": "Retrieve appointment by patient phone.",
            "caller_profile": {
                "name": "Ravi Kumar",
                "phone": "+919876543210"
            },
            "conversation_script": [
                {
                    "turn": 1,
                    "speaker": "patient",
                    "utterance": "I want to check my appointments."
                },
                {
                    "turn": 2,
                    "speaker": "agent",
                    "expected_tool_calls": ["find_patient_appointments"]
                }
            ],
            "expected_db_state": {},
            "expected_outcome": "lookup_success"
        },
        # SCN-014: Cancel Non-Existent Appointment
        {
            "id": "SCN-014",
            "name": "Cancel Non-Existent Appointment",
            "category": "error_recovery",
            "description": "Tries to cancel an appointment when none exists, graceful response.",
            "caller_profile": {
                "name": "Ghost Patient",
                "phone": "+910000000004"
            },
            "conversation_script": [
                {
                    "turn": 1,
                    "speaker": "patient",
                    "utterance": "Please cancel my appointment."
                },
                {
                    "turn": 2,
                    "speaker": "agent",
                    "expected_tool_calls": ["find_patient_appointments"]
                }
            ],
            "expected_db_state": {},
            "expected_outcome": "no_mutation"
        },
        # SCN-015: Patient Gives Wrong Phone
        {
            "id": "SCN-015",
            "name": "Patient Gives Wrong Phone",
            "category": "error_recovery",
            "description": "Patient books but gives invalid phone format, agent validates.",
            "caller_profile": {
                "name": "Bad Phone Guy",
                "phone": "9876"
            },
            "conversation_script": [
                {
                    "turn": 1,
                    "speaker": "patient",
                    "utterance": "Book Ramesh B tomorrow morning."
                },
                {
                    "turn": 2,
                    "speaker": "agent",
                    "expected_tool_calls": ["check_availability"],
                    "expected_tool_params": {
                        "doctor_name": "Dr. Ramesh B."
                    }
                },
                {
                    "turn": 3,
                    "speaker": "patient",
                    "utterance": "Book it. My phone is 9876."
                },
                {
                    "turn": 4,
                    "speaker": "agent",
                    "expected_tool_calls": ["book_appointment"],
                    "expected_tool_params": {
                        "invalid_phone": True
                    }
                }
            ],
            "expected_db_state": {},
            "expected_outcome": "validation_failed"
        },
        # SCN-016: Complete Full Flow
        {
            "id": "SCN-016",
            "name": "Complete Full Flow",
            "category": "e2e",
            "description": "Full cycle: book, then reschedule, then cancel.",
            "caller_profile": {
                "name": "Cycle Rider",
                "phone": "+919999999900"
            },
            "conversation_script": [
                {
                    "turn": 1,
                    "speaker": "patient",
                    "utterance": "Book Ramesh B tomorrow."
                },
                {
                    "turn": 2,
                    "speaker": "agent",
                    "expected_tool_calls": ["check_availability"],
                    "expected_tool_params": {
                        "doctor_name": "Dr. Ramesh B."
                    }
                },
                {
                    "turn": 3,
                    "speaker": "patient",
                    "utterance": "Book first slot."
                },
                {
                    "turn": 4,
                    "speaker": "agent",
                    "expected_tool_calls": ["book_appointment"],
                    "expected_tool_params": {
                        "doctor_name": "Dr. Ramesh B."
                    }
                },
                {
                    "turn": 5,
                    "speaker": "patient",
                    "utterance": "Reschedule me to the second available slot."
                },
                {
                    "turn": 6,
                    "speaker": "agent",
                    "expected_tool_calls": ["reschedule_appointment"]
                },
                {
                    "turn": 7,
                    "speaker": "patient",
                    "utterance": "Now cancel everything."
                },
                {
                    "turn": 8,
                    "speaker": "agent",
                    "expected_tool_calls": ["cancel_appointment"]
                }
            ],
            "expected_db_state": {
                "appointments": [
                    {
                        "patient_name": "Cycle Rider",
                        "status": "cancelled"
                    }
                ]
            },
            "expected_outcome": "cancelled"
        },
        # SCN-017: Typo in Doctor Name
        {
            "id": "SCN-017",
            "name": "Typo in Doctor Name",
            "category": "clarification",
            "description": "Patient asks for Ramesh Bee instead of Ramesh B, agent matches fuzzy name query.",
            "caller_profile": {
                "name": "Typo Patient",
                "phone": "+910000000007"
            },
            "conversation_script": [
                {
                    "turn": 1,
                    "speaker": "patient",
                    "utterance": "I want to see doctor Ramesh Bee."
                },
                {
                    "turn": 2,
                    "speaker": "agent",
                    "expected_tool_calls": ["find_doctors"],
                    "expected_tool_params": {
                        "name_query": "Ramesh Bee"
                    }
                }
            ],
            "expected_db_state": {},
            "expected_outcome": "navigated"
        },
        # SCN-018: Emergency Request Deflection
        {
            "id": "SCN-018",
            "name": "Emergency Request Deflection",
            "category": "scope_boundary",
            "description": "Patient states severe active emergency; agent deflects immediately.",
            "caller_profile": {
                "name": "Emergency Caller",
                "phone": "+910000000008"
            },
            "conversation_script": [
                {
                    "turn": 1,
                    "speaker": "patient",
                    "utterance": "I think I am having a stroke right now, my face is drooping!"
                },
                {
                    "turn": 2,
                    "speaker": "agent",
                    "expected_tool_calls": [],
                    "expected_behavior": "Urgent emergency deflection, no booking"
                }
            ],
            "expected_db_state": {},
            "expected_outcome": "deflected"
        },
        # SCN-019: Weekend Availability Request
        {
            "id": "SCN-019",
            "name": "Weekend Availability Request",
            "category": "booking",
            "description": "Patient asks for Sunday; agent guides them to weekday slots.",
            "caller_profile": {
                "name": "Weekend Asker",
                "phone": "+910000000009"
            },
            "conversation_script": [
                {
                    "turn": 1,
                    "speaker": "patient",
                    "utterance": "I want to see Ramesh B this Sunday."
                },
                {
                    "turn": 2,
                    "speaker": "agent",
                    "expected_tool_calls": ["check_availability"],
                    "expected_tool_params": {
                        "doctor_name": "Dr. Ramesh B."
                    }
                }
            ],
            "expected_db_state": {},
            "expected_outcome": "navigated"
        },
        # SCN-020: 14-Day Window Boundary
        {
            "id": "SCN-020",
            "name": "14-Day Window Boundary",
            "category": "validation",
            "description": "Patient asks for date beyond 14 days, validated and handled.",
            "caller_profile": {
                "name": "Future Asker",
                "phone": "+910000000010"
            },
            "conversation_script": [
                {
                    "turn": 1,
                    "speaker": "patient",
                    "utterance": "I want to book an appointment for 30 days from now."
                },
                {
                    "turn": 2,
                    "speaker": "agent",
                    "expected_tool_calls": [],
                    "expected_behavior": "Guide to the rolling 14 day slot limitation"
                }
            ],
            "expected_db_state": {},
            "expected_outcome": "validation_failed"
        }
    ]

    for scn in scenarios:
        filename = f"scn_{scn['id'].lower().replace('-', '_')}_{scn['name'].lower().replace(' ', '_').replace('(', '').replace(')', '').replace('+', '_')}.yaml"
        filepath = os.path.join(scenarios_dir, filename)
        with open(filepath, "w") as f:
            yaml.dump(scn, f, default_flow_style=False, sort_keys=False)
        print(f"Generated {filepath}")

if __name__ == "__main__":
    main()
