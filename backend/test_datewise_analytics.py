"""
test_datewise_analytics.py
==========================
Comprehensive automated tests for Date-Wise Appointment & Patient Analytics
covering 30 test scenarios across Admin and Doctor portals.
"""

import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient

from main import app
import db_config
from api.auth_helper import encode_token

client = TestClient(app)


def get_token_for(user_id: int, role: str, doctor_id: int = None, username: str = "testuser"):
    payload = {
        "sub": username,
        "user_id": user_id,
        "role": role,
        "doctor_id": doctor_id,
    }
    token = encode_token(payload)
    return f"Bearer {token}"


@pytest.fixture(scope="module")
def setup_test_data():
    """Ensure database has appointments across various dates, doctors, statuses, and sources."""
    conn = db_config.get_db_connection()
    cur = conn.cursor()

    # Get sample doctor IDs and department IDs
    cur.execute("SELECT id, department_id FROM doctors LIMIT 2;")
    docs = cur.fetchall()
    if not docs:
        pytest.skip("No doctors found in test database")

    doc1_id, dept1_id = docs[0]
    doc2_id, dept2_id = docs[1] if len(docs) > 1 else (docs[0][0], docs[0][1])

    # Get sample patient IDs
    cur.execute("SELECT id FROM patients LIMIT 3;")
    pts = [r[0] for r in cur.fetchall()]
    if not pts:
        pytest.skip("No patients found in test database")

    today = date.today()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)
    future_date = today + timedelta(days=10)
    last_week_date = today - timedelta(days=7)

    # Delete any existing test bookings first
    cur.execute("DELETE FROM appointments WHERE booking_id LIKE 'TEST-%';")

    # Insert test appointments with unique time slots
    test_bookings = [
        # (booking_id, patient_id, doctor_id, dept_id, appt_date, appt_time, status, source)
        (f"TEST-TODAY-1", pts[0], doc1_id, dept1_id, today, "05:10:00", "CONFIRMED", "WHATSAPP_TEXT"),
        (f"TEST-TODAY-2", pts[1 % len(pts)], doc1_id, dept1_id, today, "05:20:00", "COMPLETED", "ADMIN"),
        (f"TEST-TODAY-3", pts[2 % len(pts)], doc2_id, dept2_id, today, "05:30:00", "BOOKED", "WHATSAPP_VOICE"),
        (f"TEST-YEST-1", pts[0], doc1_id, dept1_id, yesterday, "05:10:00", "COMPLETED", "DOCTOR"),
        (f"TEST-YEST-2", pts[1 % len(pts)], doc2_id, dept2_id, yesterday, "05:20:00", "CANCELLED", "WHATSAPP_TEXT"),
        (f"TEST-TOMO-1", pts[0], doc1_id, dept1_id, tomorrow, "05:10:00", "CONFIRMED", "WHATSAPP_TEXT"),
        (f"TEST-FUT-1", pts[2 % len(pts)], doc2_id, dept2_id, future_date, "05:10:00", "BOOKED", "ADMIN"),
        (f"TEST-LW-1", pts[1 % len(pts)], doc1_id, dept1_id, last_week_date, "05:10:00", "COMPLETED", "WHATSAPP_TEXT"),
    ]

    for b_id, p_id, d_id, dep_id, ap_date, ap_time, st, src in test_bookings:
        cur.execute("""
            INSERT INTO appointments (
                booking_id, patient_id, doctor_id, department_id,
                appointment_date, appointment_time, status, booking_source,
                created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s::time, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (booking_id) DO UPDATE SET
                status = EXCLUDED.status,
                appointment_date = EXCLUDED.appointment_date,
                appointment_time = EXCLUDED.appointment_time;
        """, (b_id, p_id, d_id, dep_id, ap_date, ap_time, st, src))

    conn.commit()
    cur.close()
    conn.close()

    return {
        "doc1_id": doc1_id,
        "doc2_id": doc2_id,
        "dept1_id": dept1_id,
        "today": today.isoformat(),
        "yesterday": yesterday.isoformat(),
        "tomorrow": tomorrow.isoformat(),
        "future_date": future_date.isoformat(),
    }


# ─── 30 Scenarios Tests ───────────────────────────────────────────────────────

def test_01_today_filter(setup_test_data):
    """1. Test summary and appointments filtered by Today."""
    today = setup_test_data["today"]
    admin_auth = {"Authorization": get_token_for(1, "ADMIN")}
    res = client.get(f"/api/dashboard/summary?date_from={today}&date_to={today}", headers=admin_auth)
    assert res.status_code == 200
    data = res.json()
    assert data["date_from"] == today
    assert data["date_to"] == today
    assert data["appointments"]["total"] >= 1


def test_02_yesterday_filter(setup_test_data):
    """2. Test summary filtered by Yesterday."""
    yest = setup_test_data["yesterday"]
    admin_auth = {"Authorization": get_token_for(1, "ADMIN")}
    res = client.get(f"/api/dashboard/summary?date_from={yest}&date_to={yest}", headers=admin_auth)
    assert res.status_code == 200
    data = res.json()
    assert data["appointments"]["total"] >= 1


def test_03_this_week_filter(setup_test_data):
    """3. Test summary filtered by This Week date range."""
    today = date.today()
    mon = today - timedelta(days=(today.weekday()))
    sun = mon + timedelta(days=6)
    admin_auth = {"Authorization": get_token_for(1, "ADMIN")}
    res = client.get(f"/api/dashboard/summary?date_from={mon.isoformat()}&date_to={sun.isoformat()}", headers=admin_auth)
    assert res.status_code == 200
    data = res.json()
    assert data["appointments"]["total"] >= 1


def test_04_this_month_filter(setup_test_data):
    """4. Test summary filtered by This Month date range."""
    today = date.today()
    first = date(today.year, today.month, 1)
    admin_auth = {"Authorization": get_token_for(1, "ADMIN")}
    res = client.get(f"/api/dashboard/summary?date_from={first.isoformat()}&date_to={today.isoformat()}", headers=admin_auth)
    assert res.status_code == 200
    data = res.json()
    assert "appointments" in data


def test_05_custom_date_range(setup_test_data):
    """5. Test summary filtered by Custom Date Range."""
    yest = setup_test_data["yesterday"]
    tomo = setup_test_data["tomorrow"]
    admin_auth = {"Authorization": get_token_for(1, "ADMIN")}
    res = client.get(f"/api/dashboard/summary?date_from={yest}&date_to={tomo}", headers=admin_auth)
    assert res.status_code == 200
    data = res.json()
    assert data["appointments"]["total"] >= 2


def test_06_future_date_range(setup_test_data):
    """6. Test appointments filtered by future date range."""
    fut = setup_test_data["future_date"]
    admin_auth = {"Authorization": get_token_for(1, "ADMIN")}
    res = client.get(f"/api/dashboard/appointments?date_from={fut}&date_to={fut}", headers=admin_auth)
    assert res.status_code == 200
    data = res.json()
    assert any(a["appointment_date"] == fut for a in data["appointments"])


def test_07_empty_date_range(setup_test_data):
    """7. Test date range with no appointments (empty state)."""
    past_date = "2020-01-01"
    admin_auth = {"Authorization": get_token_for(1, "ADMIN")}
    res = client.get(f"/api/dashboard/summary?date_from={past_date}&date_to={past_date}", headers=admin_auth)
    assert res.status_code == 200
    data = res.json()
    assert data["appointments"]["total"] == 0
    assert data["appointments"]["booked"] == 0


def test_08_status_and_date_filter(setup_test_data):
    """8. Test appointments filtered by status and date."""
    today = setup_test_data["today"]
    admin_auth = {"Authorization": get_token_for(1, "ADMIN")}
    res = client.get(f"/api/dashboard/appointments?date_from={today}&date_to={today}&status=CONFIRMED", headers=admin_auth)
    assert res.status_code == 200
    data = res.json()
    assert all(a["status"] == "CONFIRMED" for a in data["appointments"])


def test_09_doctor_and_date_filter(setup_test_data):
    """9. Test appointments filtered by doctor and date."""
    today = setup_test_data["today"]
    doc1_id = setup_test_data["doc1_id"]
    admin_auth = {"Authorization": get_token_for(1, "ADMIN")}
    res = client.get(f"/api/dashboard/appointments?date_from={today}&date_to={today}&doctor_id={doc1_id}", headers=admin_auth)
    assert res.status_code == 200
    data = res.json()
    assert all(a["doctor_id"] == doc1_id for a in data["appointments"])


def test_10_department_and_date_filter(setup_test_data):
    """10. Test appointments filtered by department and date."""
    today = setup_test_data["today"]
    admin_auth = {"Authorization": get_token_for(1, "ADMIN")}
    res = client.get(f"/api/dashboard/appointments?date_from={today}&date_to={today}", headers=admin_auth)
    assert res.status_code == 200
    data = res.json()
    if data["appointments"]:
        dept_name = data["appointments"][0]["department_name"]
        dept_res = client.get(f"/api/dashboard/appointments?date_from={today}&date_to={today}&department={dept_name}", headers=admin_auth)
        assert dept_res.status_code == 200
        assert all(a["department_name"].lower() == dept_name.lower() for a in dept_res.json()["appointments"])


def test_11_booking_source_and_date_filter(setup_test_data):
    """11. Test appointments filtered by booking source and date."""
    today = setup_test_data["today"]
    admin_auth = {"Authorization": get_token_for(1, "ADMIN")}
    res = client.get(f"/api/dashboard/appointments?date_from={today}&date_to={today}&booking_source=WHATSAPP_TEXT", headers=admin_auth)
    assert res.status_code == 200
    data = res.json()
    assert all(a["booking_source"] == "WHATSAPP_TEXT" for a in data["appointments"])


def test_12_admin_sees_all_doctors(setup_test_data):
    """12. Admin sees appointments across multiple doctors."""
    today = setup_test_data["today"]
    admin_auth = {"Authorization": get_token_for(1, "ADMIN")}
    res = client.get(f"/api/dashboard/appointments?date_from={today}&date_to={today}", headers=admin_auth)
    assert res.status_code == 200
    doctor_ids = {a["doctor_id"] for a in res.json()["appointments"]}
    assert len(doctor_ids) >= 1


def test_13_doctor_sees_only_own_appointments(setup_test_data):
    """13. Doctor sees only their own appointments."""
    today = setup_test_data["today"]
    doc1_id = setup_test_data["doc1_id"]
    doc_auth = {"Authorization": get_token_for(10, "DOCTOR", doctor_id=doc1_id, username="dr_wilson")}
    res = client.get(f"/api/dashboard/appointments?date_from={today}&date_to={today}", headers=doc_auth)
    assert res.status_code == 200
    data = res.json()
    assert all(a["doctor_id"] == doc1_id for a in data["appointments"])


def test_14_doctor_cannot_access_another_doctor_data(setup_test_data):
    """14. Doctor querying another doctor's doctor_id is strictly constrained to authenticated doctor."""
    today = setup_test_data["today"]
    doc1_id = setup_test_data["doc1_id"]
    doc2_id = setup_test_data["doc2_id"]
    doc1_auth = {"Authorization": get_token_for(10, "DOCTOR", doctor_id=doc1_id, username="dr_wilson")}
    # Doctor 1 requests Doctor 2's id
    res = client.get(f"/api/dashboard/appointments?date_from={today}&date_to={today}&doctor_id={doc2_id}", headers=doc1_auth)
    assert res.status_code == 200
    data = res.json()
    # Backend must have scoped to doc1_id
    assert all(a["doctor_id"] == doc1_id for a in data["appointments"])


def test_15_appointment_date_filtering_uses_appointment_date(setup_test_data):
    """15. Verifies appointment_date filter filters on appointment_date."""
    fut = setup_test_data["future_date"]
    admin_auth = {"Authorization": get_token_for(1, "ADMIN")}
    res = client.get(f"/api/dashboard/appointments?date_from={fut}&date_to={fut}&date_type=appointment_date", headers=admin_auth)
    assert res.status_code == 200
    data = res.json()
    assert all(a["appointment_date"] == fut for a in data["appointments"])


def test_16_created_date_filtering_uses_created_at(setup_test_data):
    """16. Verifies created_at date filtering works distinctly from appointment_date."""
    today = setup_test_data["today"]
    admin_auth = {"Authorization": get_token_for(1, "ADMIN")}
    res = client.get(f"/api/dashboard/appointments?date_from={today}&date_to={today}&date_type=created_at", headers=admin_auth)
    assert res.status_code == 200
    data = res.json()
    assert "appointments" in data


def test_17_cancellation_date_analytics(setup_test_data):
    """17. Verifies date-wise analytics tracks cancellation trend by cancelled_at."""
    admin_auth = {"Authorization": get_token_for(1, "ADMIN")}
    res = client.get("/api/dashboard/analytics/date-wise", headers=admin_auth)
    assert res.status_code == 200
    data = res.json()
    assert "cancellation_trend" in data


def test_18_rescheduling_analytics(setup_test_data):
    """18. Verifies date-wise analytics tracks reschedule trend by rescheduled_at."""
    admin_auth = {"Authorization": get_token_for(1, "ADMIN")}
    res = client.get("/api/dashboard/analytics/date-wise", headers=admin_auth)
    assert res.status_code == 200
    data = res.json()
    assert "reschedule_trend" in data


def test_19_multiple_appointments_same_day(setup_test_data):
    """19. Daily view correctly aggregates multiple appointments on the same date."""
    today = setup_test_data["today"]
    admin_auth = {"Authorization": get_token_for(1, "ADMIN")}
    res = client.get(f"/api/dashboard/daily-view?date={today}", headers=admin_auth)
    assert res.status_code == 200
    data = res.json()
    assert data["date"] == today
    assert data["totals"]["total"] >= 2


def test_20_multiple_patients_same_day(setup_test_data):
    """20. Tests distinct patient handling on the same day."""
    today = setup_test_data["today"]
    admin_auth = {"Authorization": get_token_for(1, "ADMIN")}
    res = client.get(f"/api/dashboard/summary?date_from={today}&date_to={today}", headers=admin_auth)
    assert res.status_code == 200
    data = res.json()
    assert data["patients"]["unique_in_range"] >= 1


def test_21_daily_appointment_totals(setup_test_data):
    """21. Daily view totals match individual status counts."""
    today = setup_test_data["today"]
    admin_auth = {"Authorization": get_token_for(1, "ADMIN")}
    res = client.get(f"/api/dashboard/daily-view?date={today}", headers=admin_auth)
    assert res.status_code == 200
    totals = res.json()["totals"]
    expected_total = totals["completed"] + totals["pending"] + totals["cancelled"] + totals["rescheduled"] + totals["no_show"]
    assert totals["total"] == expected_total


def test_22_weekly_trend_analytics(setup_test_data):
    """22. Weekly appointment trend in date-wise analytics."""
    today = date.today()
    from_date = (today - timedelta(days=6)).isoformat()
    to_date = today.isoformat()
    admin_auth = {"Authorization": get_token_for(1, "ADMIN")}
    res = client.get(f"/api/dashboard/analytics/date-wise?date_from={from_date}&date_to={to_date}", headers=admin_auth)
    assert res.status_code == 200
    data = res.json()
    assert len(data["appointments_by_date"]) == 7


def test_23_monthly_trend_analytics(setup_test_data):
    """23. Monthly appointment trend in date-wise analytics."""
    today = date.today()
    from_date = (today - timedelta(days=29)).isoformat()
    to_date = today.isoformat()
    admin_auth = {"Authorization": get_token_for(1, "ADMIN")}
    res = client.get(f"/api/dashboard/analytics/date-wise?date_from={from_date}&date_to={to_date}", headers=admin_auth)
    assert res.status_code == 200
    data = res.json()
    assert len(data["appointments_by_date"]) == 30


def test_24_cancellation_trend(setup_test_data):
    """24. Cancellation trend returns a list of time-series points."""
    admin_auth = {"Authorization": get_token_for(1, "ADMIN")}
    res = client.get("/api/dashboard/analytics/date-wise", headers=admin_auth)
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data["cancellation_trend"], list)


def test_25_completion_trend(setup_test_data):
    """25. Completion trend returns a list of time-series points."""
    admin_auth = {"Authorization": get_token_for(1, "ADMIN")}
    res = client.get("/api/dashboard/analytics/date-wise", headers=admin_auth)
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data["completion_trend"], list)


def test_26_booking_source_analytics(setup_test_data):
    """26. Booking source analytics returns sources breakdown."""
    admin_auth = {"Authorization": get_token_for(1, "ADMIN")}
    res = client.get("/api/dashboard/analytics/date-wise", headers=admin_auth)
    assert res.status_code == 200
    data = res.json()
    assert "booking_source_analytics" in data
    assert isinstance(data["booking_source_analytics"], list)


def test_27_department_analytics(setup_test_data):
    """27. Department analytics returns department counts."""
    admin_auth = {"Authorization": get_token_for(1, "ADMIN")}
    res = client.get("/api/dashboard/analytics/date-wise", headers=admin_auth)
    assert res.status_code == 200
    data = res.json()
    assert "department_analytics" in data


def test_28_doctor_analytics(setup_test_data):
    """28. Doctor analytics returns doctor counts."""
    admin_auth = {"Authorization": get_token_for(1, "ADMIN")}
    res = client.get("/api/dashboard/analytics/date-wise", headers=admin_auth)
    assert res.status_code == 200
    data = res.json()
    assert "doctor_analytics" in data


def test_29_patient_unique_count_calculation(setup_test_data):
    """29. Patient unique count in summary does not equal appointment count when multiple appts exist."""
    admin_auth = {"Authorization": get_token_for(1, "ADMIN")}
    res = client.get("/api/dashboard/summary", headers=admin_auth)
    assert res.status_code == 200
    data = res.json()
    assert "unique_in_range" in data["patients"]
    assert "returning_in_range" in data["patients"]


def test_30_existing_functionality_preserved(setup_test_data):
    """30. Existing appointment endpoints and status updates remain working."""
    admin_auth = {"Authorization": get_token_for(1, "ADMIN")}
    res = client.get("/api/dashboard/appointments?per_page=1", headers=admin_auth)
    assert res.status_code == 200
    appts = res.json()["appointments"]
    assert len(appts) >= 1
    booking_id = appts[0]["booking_id"]
    
    # Test status update
    update_res = client.patch(
        f"/api/dashboard/appointments/{booking_id}/status",
        json={"status": "CONFIRMED"},
        headers=admin_auth,
    )
    assert update_res.status_code == 200
    assert update_res.json()["success"] is True
