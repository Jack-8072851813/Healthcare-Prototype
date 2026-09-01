"""
test_voice.py
=============
Automated test suite for Step 5.2 — Multilingual Voice Processing.

Contains 20 validation scenarios:
  1-7:   Multilingual voice pipelines (EN, TA, HI, TE, ML, KN, UR)
  8:     Voice greeting
  9:     Voice new patient flow
  10:    Voice existing patient flow
  11:    Voice appointment
  12:    Voice doctor availability
  13:    Voice cancellation
  14:    Voice rescheduling
  15:    Voice hospital information
  16:    Voice RAG query
  17:    Voice emergency
  18:    Voice context preservation
  19:    Voice language switching
  20:    Invalid audio handling

Run:
    python test_voice.py

Step 5.2 — Meridian Hospital POC
"""

import sys
import os
import uuid
import datetime

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import db_config
import voice.voice_service as voice_service

passed_tests = []
failed_tests = []


def log_result(name, passed, detail=""):
    if passed:
        passed_tests.append(name)
        print(f"[PASS] {name}")
    else:
        failed_tests.append(name)
        print(f"[FAIL] {name}" + (f" - {detail}" if detail else ""))


def run_voice_test_pipeline(filename: str, session_id: str, patient_code: str = None, language: str = None) -> dict:
    """Helper to simulate voice audio file upload pipeline."""
    scratch_dir = os.path.join(backend_dir, "scratch")
    os.makedirs(scratch_dir, exist_ok=True)
    temp_file_path = os.path.join(scratch_dir, filename)
    
    # Create empty dummy audio file for testing
    with open(temp_file_path, "wb") as f:
        f.write(b"RIFF\x24\x08\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x40\x1f\x00\x00\x80\x3e\x00\x00\x02\x00\x10\x00data\x00\x08\x00\x00")
        
    try:
        res = voice_service.process_voice_input(
            audio_file_path=temp_file_path,
            session_id=session_id,
            patient_code=patient_code,
            language_override=language
        )
        return res
    finally:
        # Clean up
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass


def run_tests():
    # Setup database clean state for dynamic patients to avoid greeting bypass
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM appointments WHERE patient_id IN (SELECT id FROM patients WHERE whatsapp_number = '919999999999' OR phone = '919999999999');")
        cur.execute("DELETE FROM patients WHERE whatsapp_number = '919999999999' OR phone = '919999999999';")
        conn.commit()
    except Exception as e:
        conn.rollback()
    finally:
        cur.close()
        conn.close()

    # 1. English voice pipeline
    try:
        session_id = f"VCONV_{uuid.uuid4().hex[:6]}"
        res = run_voice_test_pipeline("english_timing.wav", session_id, language="ENGLISH")
        ok = (
            res["success"] and 
            res["transcript"] == "What are the hospital timings?" and
            res["language"] == "ENGLISH" and
            "opd" in res["response_text"].lower() and
            res["audio"].startswith("data:audio/")
        )
        log_result("Scenario 1: English voice pipeline", ok)
    except Exception as e:
        log_result("Scenario 1: English voice pipeline", False, str(e))

    # 2. Tamil voice pipeline
    try:
        session_id = f"VCONV_{uuid.uuid4().hex[:6]}"
        res = run_voice_test_pipeline("tamil_where.wav", session_id, language="TAMIL")
        ok = (
            res["success"] and
            res["transcript"] == "மருத்துவமனை எங்கே உள்ளது?" and
            res["language"] == "TAMIL" and
            res["audio"].startswith("data:audio/")
        )
        log_result("Scenario 2: Tamil voice pipeline", ok)
    except Exception as e:
        log_result("Scenario 2: Tamil voice pipeline", False, str(e))

    # 3. Hindi voice pipeline
    try:
        session_id = f"VCONV_{uuid.uuid4().hex[:6]}"
        res = run_voice_test_pipeline("hindi_greet.wav", session_id, language="HINDI")
        ok = (
            res["success"] and
            res["transcript"] == "नमस्ते" and
            res["language"] == "HINDI" and
            res["audio"].startswith("data:audio/")
        )
        log_result("Scenario 3: Hindi voice pipeline", ok)
    except Exception as e:
        log_result("Scenario 3: Hindi voice pipeline", False, str(e))

    # 4. Telugu voice pipeline
    try:
        session_id = f"VCONV_{uuid.uuid4().hex[:6]}"
        res = run_voice_test_pipeline("telugu_where.wav", session_id, language="TELUGU")
        ok = (
            res["success"] and
            res["transcript"] == "ఆసుపత్రి ఎక్కడ ఉంది?" and
            res["language"] == "TELUGU" and
            res["audio"].startswith("data:audio/")
        )
        log_result("Scenario 4: Telugu voice pipeline", ok)
    except Exception as e:
        log_result("Scenario 4: Telugu voice pipeline", False, str(e))

    # 5. Malayalam voice pipeline
    try:
        session_id = f"VCONV_{uuid.uuid4().hex[:6]}"
        res = run_voice_test_pipeline("malayalam_where.wav", session_id, language="MALAYALAM")
        ok = (
            res["success"] and
            res["transcript"] == "ആശുപത്രി എവിടെ ആണ്?" and
            res["language"] == "MALAYALAM" and
            res["audio"].startswith("data:audio/")
        )
        log_result("Scenario 5: Malayalam voice pipeline", ok)
    except Exception as e:
        log_result("Scenario 5: Malayalam voice pipeline", False, str(e))

    # 6. Kannada voice pipeline
    try:
        session_id = f"VCONV_{uuid.uuid4().hex[:6]}"
        res = run_voice_test_pipeline("kannada_where.wav", session_id, language="KANNADA")
        ok = (
            res["success"] and
            res["transcript"] == "ಆಸ್ಪತ್ರೆ ಎಲ್ಲಿದೆ?" and
            res["language"] == "KANNADA" and
            res["audio"].startswith("data:audio/")
        )
        log_result("Scenario 6: Kannada voice pipeline", ok)
    except Exception as e:
        log_result("Scenario 6: Kannada voice pipeline", False, str(e))

    # 7. Urdu voice pipeline
    try:
        session_id = f"VCONV_{uuid.uuid4().hex[:6]}"
        res = run_voice_test_pipeline("urdu_where.wav", session_id, language="URDU")
        ok = (
            res["success"] and
            res["transcript"] == "ہسپتال کہاں ہے؟" and
            res["language"] == "URDU" and
            res["audio"].startswith("data:audio/")
        )
        log_result("Scenario 7: Urdu voice pipeline", ok)
    except Exception as e:
        log_result("Scenario 7: Urdu voice pipeline", False, str(e))

    # 8. Voice greeting
    try:
        session_id = f"VCONV_{uuid.uuid4().hex[:6]}"
        res = run_voice_test_pipeline("english_greet.wav", session_id)
        ok = (
            res["success"] and
            res["intent"] == "GREETING" and
            "Welcome to Meridian Hospital" in res["response_text"]
        )
        log_result("Scenario 8: Voice greeting", ok)
    except Exception as e:
        log_result("Scenario 8: Voice greeting", False, str(e))

    # 9. Voice new patient flow
    try:
        session_id = f"VCONV_{uuid.uuid4().hex[:6]}"
        run_voice_test_pipeline("english_greet.wav", session_id)
        # Patient says "I am new"
        res = run_voice_test_pipeline("tamil_new.wav", session_id) # "நான் புதிய நோயாளி"
        ok = (
            res["success"] and
            res["intent"] == "REGISTER_PATIENT" and
            res["language"] == "TAMIL"
        )
        log_result("Scenario 9: Voice new patient flow", ok)
    except Exception as e:
        log_result("Scenario 9: Voice new patient flow", False, str(e))

    # 10. Voice existing patient flow
    try:
        session_id = f"VCONV_{uuid.uuid4().hex[:6]}"
        res = run_voice_test_pipeline("english_greet.wav", session_id, patient_code="P001")
        # Direct patient registration identification bypass
        ok = (
            res["success"] and
            res["intent"] == "GREETING" and
            "Ramesh" in res["response_text"]
        )
        log_result("Scenario 10: Voice existing patient flow", ok)
    except Exception as e:
        log_result("Scenario 10: Voice existing patient flow", False, str(e))

    # 11. Voice appointment
    try:
        session_id = f"VCONV_{uuid.uuid4().hex[:6]}"
        res = run_voice_test_pipeline("english_appointment.wav", session_id, patient_code="P001")
        ok = (
            res["success"] and
            res["intent"] == "BOOK_APPOINTMENT" and
            "department or doctor" in res["response_text"].lower()
        )
        log_result("Scenario 11: Voice appointment", ok)
    except Exception as e:
        log_result("Scenario 11: Voice appointment", False, str(e))

    # 12. Voice doctor availability
    try:
        session_id = f"VCONV_{uuid.uuid4().hex[:6]}"
        res = run_voice_test_pipeline("english_doctor.wav", session_id, patient_code="P001")
        ok = (
            res["success"] and
            res["intent"] == "DOCTOR_AVAILABILITY" and
            "scheduled" in res["response_text"].lower()
        )
        log_result("Scenario 12: Voice doctor availability", ok)
    except Exception as e:
        log_result("Scenario 12: Voice doctor availability", False, str(e))

    # 13. Voice cancellation
    try:
        session_id = f"VCONV_{uuid.uuid4().hex[:6]}"
        res = run_voice_test_pipeline("english_cancel.wav", session_id, patient_code="P001")
        ok = (
            res["success"] and
            res["intent"] == "CANCEL_APPOINTMENT" and
            "booking id" in res["response_text"].lower()
        )
        log_result("Scenario 13: Voice cancellation", ok)
    except Exception as e:
        log_result("Scenario 13: Voice cancellation", False, str(e))

    # 14. Voice rescheduling
    try:
        session_id = f"VCONV_{uuid.uuid4().hex[:6]}"
        res = run_voice_test_pipeline("english_reschedule.wav", session_id, patient_code="P001")
        ok = (
            res["success"] and
            res["intent"] == "RESCHEDULE_APPOINTMENT" and
            "booking id" in res["response_text"].lower()
        )
        log_result("Scenario 14: Voice rescheduling", ok)
    except Exception as e:
        log_result("Scenario 14: Voice rescheduling", False, str(e))

    # 15. Voice hospital information
    try:
        session_id = f"VCONV_{uuid.uuid4().hex[:6]}"
        res = run_voice_test_pipeline("english_location.wav", session_id, patient_code="P001")
        ok = (
            res["success"] and
            res["intent"] == "HOSPITAL_INFORMATION" and
            "sector 4" in res["response_text"].lower()
        )
        log_result("Scenario 15: Voice hospital information", ok)
    except Exception as e:
        log_result("Scenario 15: Voice hospital information", False, str(e))

    # 16. Voice RAG query
    try:
        session_id = f"VCONV_{uuid.uuid4().hex[:6]}"
        res = run_voice_test_pipeline("tamil_departments.wav", session_id, patient_code="P001")
        ok = (
            res["success"] and
            res["intent"] == "HOSPITAL_INFORMATION" and
            "துறை" in res["response_text"] # matches "துறைகள்" or "துறைகளில்"
        )
        log_result("Scenario 16: Voice RAG query", ok)
    except Exception as e:
        log_result("Scenario 16: Voice RAG query", False, str(e))

    # 17. Voice emergency
    try:
        session_id = f"VCONV_{uuid.uuid4().hex[:6]}"
        res = run_voice_test_pipeline("english_chest_pain.wav", session_id)
        ok = (
            res["success"] and
            res["intent"] in ["EMERGENCY_GUIDANCE", "SYMPTOM_GUIDANCE"] and
            ("immediately" in res["response_text"].lower() or "112" in res["response_text"])
        )
        log_result("Scenario 17: Voice emergency", ok)
    except Exception as e:
        log_result("Scenario 17: Voice emergency", False, str(e))

    # 18. Voice context preservation
    try:
        session_id = f"VCONV_{uuid.uuid4().hex[:6]}"
        run_voice_test_pipeline("english_appointment.wav", session_id, patient_code="P001")
        # Second turn: "General Medicine tomorrow at 09:00 AM"
        res = run_voice_test_pipeline("english_tomorrow.wav", session_id)
        # Should preserve intent BOOK_APPOINTMENT
        ok = (
            res["success"] and
            res["intent"] == "BOOK_APPOINTMENT"
        )
        log_result("Scenario 18: Voice context preservation", ok)
    except Exception as e:
        log_result("Scenario 18: Voice context preservation", False, str(e))

    # 19. Voice language switching
    try:
        session_id = f"VCONV_{uuid.uuid4().hex[:6]}"
        run_voice_test_pipeline("english_location.wav", session_id, patient_code="P001")
        # switch to Tamil
        res = run_voice_test_pipeline("tamil_switch.wav", session_id) # "தமிழில் சொல்லுங்கள்"
        ok = (
            res["success"] and
            res["language"] == "TAMIL"
        )
        log_result("Scenario 19: Voice language switching", ok)
    except Exception as e:
        log_result("Scenario 19: Voice language switching", False, str(e))

    # 20. Invalid audio handling
    try:
        # Invalid / missing filename lookup
        session_id = f"VCONV_{uuid.uuid4().hex[:6]}"
        res = run_voice_test_pipeline("garbage_gibberish_noise.wav", session_id)
        # Falls back to default greeting or graceful notice
        ok = (
            res["success"] and
            res["response_text"] is not None and
            len(res["response_text"]) > 10
        )
        log_result("Scenario 20: Invalid audio handling", ok)
    except Exception as e:
        log_result("Scenario 20: Invalid audio handling", False, str(e))

    print("\n=== VOICE SUITE SUMMARY ===")
    print(f"Passed: {len(passed_tests)}/20")
    print(f"Failed: {len(failed_tests)}/20")
    return len(failed_tests) == 0


if __name__ == "__main__":
    success = run_tests()
    if not success:
        sys.exit(1)
    print("\nAll 20 Voice Processing verifications passed successfully!")
    sys.exit(0)
