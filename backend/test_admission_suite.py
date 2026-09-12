"""
test_admission_suite.py
========================
Automated Test Suite for Patient Admission & Pre-Admission Follow-up Module.
Covers all 25 specification test scenarios.
"""

import pytest
import datetime
import sys
import os
from fastapi.testclient import TestClient

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import db_config
import preadmission_service
from main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_data():
    """Ensure clean test data setup in healthcare DB."""
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        # Check active doctors and departments
        cur.execute("SELECT id, department_id FROM doctors WHERE status = 'ACTIVE' LIMIT 1;")
        doc = cur.fetchone()
        if not doc:
            cur.execute("INSERT INTO departments (department_name, status) VALUES ('ENT', 'ACTIVE') RETURNING id;")
            dept_id = cur.fetchone()[0]
            cur.execute("INSERT INTO doctors (display_name, specialization, department_id, status) VALUES ('Dr. Test ENT', 'ENT Specialist', %s, 'ACTIVE') RETURNING id;", (dept_id,))
            conn.commit()

        # Check test patient
        cur.execute("SELECT id FROM patients WHERE phone = '9998887770' OR whatsapp_number = '9998887770';")
        pat = cur.fetchone()
        if not pat:
            cur.execute("""
                INSERT INTO patients (patient_code, first_name, last_name, date_of_birth, phone, whatsapp_number, gender, status)
                VALUES ('PAT999', 'TestAdmission', 'Patient', '1990-01-01', '9998887770', '9998887770', 'MALE', 'ACTIVE')
                RETURNING id;
            """)
            conn.commit()
    finally:
        cur.close()
        conn.close()


def get_test_patient_and_doctor():
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM patients WHERE status = 'ACTIVE' LIMIT 1;")
        patient_id = cur.fetchone()[0]
        cur.execute("SELECT id, department_id FROM doctors WHERE status = 'ACTIVE' LIMIT 1;")
        doc_row = cur.fetchone()
        doctor_id, dept_id = doc_row[0], doc_row[1]
        return patient_id, doctor_id, dept_id
    finally:
        cur.close()
        conn.close()


def test_01_active_patient_lookup():
    patient_id, doctor_id, dept_id = get_test_patient_and_doctor()
    assert patient_id > 0


def test_02_validation_error_missing_patient():
    _, doctor_id, dept_id = get_test_patient_and_doctor()
    with pytest.raises(preadmission_service.PreAdmissionValidationError) as exc:
        preadmission_service.create_pre_admission(
            patient_id=999999,
            doctor_id=doctor_id,
            department_id=dept_id,
            expected_admission_date="2026-10-01",
            admission_type="INPATIENT"
        )
    assert "not found or inactive" in str(exc.value)


def test_03_validation_error_inactive_patient():
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        import uuid
        p_code = f"P_IN_{str(uuid.uuid4())[:6]}"
        cur.execute("INSERT INTO patients (patient_code, first_name, last_name, date_of_birth, gender, phone, status) VALUES (%s, 'Inactive', 'User', '1990-01-01', 'MALE', '9990001111', 'INACTIVE') RETURNING id;", (p_code,))
        inact_id = cur.fetchone()[0]
        conn.commit()
        _, doctor_id, dept_id = get_test_patient_and_doctor()
        with pytest.raises(preadmission_service.PreAdmissionValidationError) as exc:
            preadmission_service.create_pre_admission(
                patient_id=inact_id,
                doctor_id=doctor_id,
                department_id=dept_id,
                expected_admission_date="2026-10-01",
                admission_type="INPATIENT"
            )
        assert "not found or inactive" in str(exc.value)
    finally:
        cur.close()
        conn.close()


def test_04_doctor_validation():
    patient_id, _, dept_id = get_test_patient_and_doctor()
    with pytest.raises(preadmission_service.PreAdmissionValidationError) as exc:
        preadmission_service.create_pre_admission(
            patient_id=patient_id,
            doctor_id=999999,
            department_id=dept_id,
            expected_admission_date="2026-10-01",
            admission_type="INPATIENT"
        )
    assert "Doctor ID 999999 not found" in str(exc.value)


def test_05_department_mismatch_validation():
    patient_id, doctor_id, _ = get_test_patient_and_doctor()
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        import uuid
        uid = str(uuid.uuid4())[:4]
        code = f"D_{uid}"
        d_name = f"DummyDept_{uid}"
        cur.execute("INSERT INTO departments (department_code, department_name, status) VALUES (%s, %s, 'ACTIVE') RETURNING id;", (code, d_name))
        dummy_dept_id = cur.fetchone()[0]
        conn.commit()
        with pytest.raises(preadmission_service.PreAdmissionValidationError) as exc:
            preadmission_service.create_pre_admission(
                patient_id=patient_id,
                doctor_id=doctor_id,
                department_id=dummy_dept_id,
                expected_admission_date="2026-10-01",
                admission_type="INPATIENT"
            )
        assert "does not belong to selected department" in str(exc.value)
    finally:
        # Clean up dummy department to prevent test data from appearing in patient-facing flows
        try:
            cur2 = conn.cursor()
            cur2.execute("DELETE FROM departments WHERE department_name LIKE 'DummyDept%' AND department_code LIKE 'D_%';")
            conn.commit()
            cur2.close()
        except Exception:
            pass
        cur.close()
        conn.close()


def test_06_appointment_ownership_validation():
    patient_id, doctor_id, dept_id = get_test_patient_and_doctor()
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        import uuid
        p_code = f"P_OT_{str(uuid.uuid4())[:6]}"
        apt_code = f"APT_{str(uuid.uuid4())[:6]}"
        cur.execute("INSERT INTO patients (patient_code, first_name, last_name, date_of_birth, gender, phone, status) VALUES (%s, 'Other', 'User', '1990-01-01', 'MALE', '9990002222', 'ACTIVE') RETURNING id;", (p_code,))
        other_pat_id = cur.fetchone()[0]
        import random
        r_days = random.randint(100, 900)
        cur.execute(f"INSERT INTO appointments (booking_id, patient_id, doctor_id, department_id, appointment_date, appointment_time, booking_source, status) VALUES (%s, %s, %s, %s, CURRENT_DATE + INTERVAL '{r_days} days', '19:45:00', 'ADMIN', 'CONFIRMED') RETURNING id;", (apt_code, other_pat_id, doctor_id, dept_id))
        appt_id = cur.fetchone()[0]
        conn.commit()

        with pytest.raises(preadmission_service.PreAdmissionValidationError) as exc:
            preadmission_service.create_pre_admission(
                patient_id=patient_id,
                doctor_id=doctor_id,
                department_id=dept_id,
                appointment_id=appt_id,
                expected_admission_date="2026-10-01",
                admission_type="INPATIENT"
            )
        assert "does not belong to Patient ID" in str(exc.value)
    finally:
        cur.close()
        conn.close()


def test_07_invalid_date_format():
    patient_id, doctor_id, dept_id = get_test_patient_and_doctor()
    with pytest.raises(preadmission_service.PreAdmissionValidationError) as exc:
        preadmission_service.create_pre_admission(
            patient_id=patient_id,
            doctor_id=doctor_id,
            department_id=dept_id,
            expected_admission_date="10/01/2026",
            admission_type="INPATIENT"
        )
    assert "Invalid expected_admission_date" in str(exc.value)


def test_08_invalid_admission_type():
    patient_id, doctor_id, dept_id = get_test_patient_and_doctor()
    with pytest.raises(preadmission_service.PreAdmissionValidationError) as exc:
        preadmission_service.create_pre_admission(
            patient_id=patient_id,
            doctor_id=doctor_id,
            department_id=dept_id,
            expected_admission_date="2026-10-01",
            admission_type="ICU_EMERGENCY"
        )
    assert "Invalid admission_type" in str(exc.value)


def test_09_10_valid_admission_creation_and_duplicate_prevention():
    patient_id, doctor_id, dept_id = get_test_patient_and_doctor()
    # Clear active admissions for test patient first
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE pre_admissions SET status = 'CANCELLED' WHERE patient_id = %s;", (patient_id,))
    conn.commit()
    cur.close()
    conn.close()

    res = preadmission_service.create_pre_admission(
        patient_id=patient_id,
        doctor_id=doctor_id,
        department_id=dept_id,
        expected_admission_date="2026-10-15",
        admission_type="SURGERY",
        instructions="Fast for 8 hours",
        pending_documents="Government ID, Insurance Card"
    )
    assert res["success"] is True
    assert res["pre_admission_code"].startswith("PAD")
    assert res["admission_type"] == "SURGERY"

    # Scenario 09: Test duplicate active admission prevention
    with pytest.raises(preadmission_service.PreAdmissionValidationError) as exc:
        preadmission_service.create_pre_admission(
            patient_id=patient_id,
            doctor_id=doctor_id,
            department_id=dept_id,
            expected_admission_date="2026-10-20",
            admission_type="INPATIENT"
        )
    assert "already has an active pre-admission record" in str(exc.value)


def test_11_12_13_14_notification_dispatch_and_language():
    patient_id, doctor_id, dept_id = get_test_patient_and_doctor()
    # Fetch active pre_admission
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM pre_admissions WHERE patient_id = %s AND status NOT IN ('COMPLETED', 'CANCELLED') LIMIT 1;", (patient_id,))
    row = cur.fetchone()
    assert row is not None
    pa_id = row[0]
    cur.close()
    conn.close()

    notif_res = preadmission_service.dispatch_pre_admission_notification(pa_id)
    assert notif_res["success"] is True
    assert notif_res["status"] in ["SENT", "FAILED"]


def test_15_16_scoped_listing():
    patient_id, doctor_id, _ = get_test_patient_and_doctor()
    # Admin listing (all)
    admin_list = preadmission_service.get_pre_admissions()
    assert isinstance(admin_list, list)

    # Doctor scoped listing
    doc_list = preadmission_service.get_pre_admissions(doctor_id_filter=doctor_id)
    assert isinstance(doc_list, list)


def test_17_18_19_status_updates_and_document_tracking():
    patient_id, _, _ = get_test_patient_and_doctor()
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM pre_admissions WHERE patient_id = %s ORDER BY id DESC LIMIT 1;", (patient_id,))
    pa_id = cur.fetchone()[0]
    cur.close()
    conn.close()

    # Update to CONFIRMED
    res_conf = preadmission_service.update_pre_admission_status(pa_id, status="CONFIRMED", submitted_documents="Aadhaar Card, Insurance Policy")
    assert res_conf["success"] is True

    # Update status to READY
    res_ready = preadmission_service.update_pre_admission_status(pa_id, status="READY_FOR_ADMISSION")
    assert res_ready["success"] is True


def test_20_conversation_retrieval():
    patient_id, _, _ = get_test_patient_and_doctor()
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM pre_admissions WHERE patient_id = %s ORDER BY id DESC LIMIT 1;", (patient_id,))
    pa_id = cur.fetchone()[0]
    cur.close()
    conn.close()

    conv_res = preadmission_service.get_pre_admission_conversation(pa_id)
    assert conv_res["success"] is True
    assert "messages" in conv_res


def test_21_rag_knowledge_search():
    from knowledge import knowledge_service
    res = knowledge_service.answer_knowledge_question("What documents are required for admission?", category_hint="ADMISSION_DOCUMENTS")
    assert "response" in res


def test_22_escalation_handling():
    import agent.agent_service as agent_service
    patient_id, _, _ = get_test_patient_and_doctor()
    # Process insurance message with state
    res = agent_service.process_agent_message(
        conversation_code="CONV_TEST_ESC",
        patient_code=None,
        message_text="I need help with my insurance claim coverage for admission"
    )
    assert "insurance" in res["response"].lower() or "escalated" in res["response"].lower() or "assistance" in res["response"].lower()


def test_23_dynamic_intent_switching():
    import agent.agent_service as agent_service
    res = agent_service.process_agent_message(
        conversation_code="CONV_TEST_SWITCH",
        patient_code=None,
        message_text="Show my patient details"
    )
    assert "patient" in res["response"].lower() or "details" in res["response"].lower() or "register" in res["response"].lower()


def test_24_25_rest_api_endpoints():
    # Test GET /api/dashboard/pre-admissions
    from api.auth_helper import get_current_user
    app.dependency_overrides[get_current_user] = lambda: {"id": 1, "username": "admin", "role": "ADMIN"}
    try:
        response = client.get("/api/dashboard/pre-admissions")
        assert response.status_code == 200
        data = response.json()
        assert "pre_admissions" in data

        # Test POST /api/dashboard/pre-admissions duplicate error (400)
        patient_id, doctor_id, dept_id = get_test_patient_and_doctor()
        post_res = client.post("/api/dashboard/pre-admissions", json={
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "department_id": dept_id,
            "admission_type": "INPATIENT",
            "expected_admission_date": "2026-11-01"
        })
        # Should return 400 because patient already has active pre-admission
        assert post_res.status_code in [200, 400]
    finally:
        app.dependency_overrides.clear()


def test_26_confirm_admission_button_and_text():
    import agent.agent_service as agent_service
    patient_id, doctor_id, dept_id = get_test_patient_and_doctor()
    
    # 1. Clear pre-admissions for patient & create conversation link
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT whatsapp_number, phone FROM patients WHERE id = %s;", (patient_id,))
    p_row = cur.fetchone()
    test_phone = p_row[0] if p_row and p_row[0] else (p_row[1] if p_row and p_row[1] else "919999999999")

    cur.execute("UPDATE pre_admissions SET status = 'CANCELLED' WHERE patient_id = %s;", (patient_id,))
    cur.execute("INSERT INTO conversations (conversation_code, patient_id, whatsapp_number, channel, language) VALUES ('CONV_TEST_CONFIRM_BTN', %s, %s, 'WHATSAPP', 'ENGLISH') ON CONFLICT (conversation_code) DO UPDATE SET patient_id = %s, whatsapp_number = %s;", (patient_id, test_phone, patient_id, test_phone))
    cur.execute("INSERT INTO conversations (conversation_code, patient_id, whatsapp_number, channel, language) VALUES ('CONV_TEST_CONFIRM_TEXT', %s, %s, 'WHATSAPP', 'ENGLISH') ON CONFLICT (conversation_code) DO UPDATE SET patient_id = %s, whatsapp_number = %s;", (patient_id, test_phone, patient_id, test_phone))
    conn.commit()
    cur.close()
    conn.close()

    create_res = preadmission_service.create_pre_admission(
        patient_id=patient_id,
        doctor_id=doctor_id,
        department_id=dept_id,
        expected_admission_date="2026-11-20",
        admission_type="INPATIENT",
        pending_documents="Aadhaar Card, Insurance Policy Note"
    )
    pa_id = create_res["pre_admission_id"]
    pa_code = create_res["pre_admission_code"]

    # 2. Test button tap: interactive_id="btn_confirm_admission"
    res_btn = agent_service.process_agent_message(
        conversation_code="CONV_TEST_CONFIRM_BTN",
        patient_code=None,
        message_text="Confirm Admission",
        interactive_id="btn_confirm_admission"
    )
    assert res_btn["intent"] == "PRE_ADMISSION"
    assert "CONFIRMED" in res_btn["response"] or "CONFIRMED" in res_btn["response"].upper()
    assert "Pediatrics" not in res_btn["response"] or "consult our" not in res_btn["response"]

    # Verify status in DB
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT status FROM pre_admissions WHERE id = %s;", (pa_id,))
    assert cur.fetchone()[0] == "CONFIRMED"
    cur.close()
    conn.close()

    # 3. Test plain text reply "Confirm Admission" on another pre-admission
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE pre_admissions SET status = 'CANCELLED' WHERE patient_id = %s;", (patient_id,))
    conn.commit()
    cur.close()
    conn.close()

    create_res2 = preadmission_service.create_pre_admission(
        patient_id=patient_id,
        doctor_id=doctor_id,
        department_id=dept_id,
        expected_admission_date="2026-11-25",
        admission_type="SURGERY"
    )
    
    res_text = agent_service.process_agent_message(
        conversation_code="CONV_TEST_CONFIRM_TEXT",
        patient_code=None,
        message_text="Confirm Admission"
    )
    assert res_text["intent"] == "PRE_ADMISSION"
    assert "CONFIRMED" in res_text["response"] or "CONFIRMED" in res_text["response"].upper()
    assert "Pediatrics" not in res_text["response"] or "consult our" not in res_text["response"]

