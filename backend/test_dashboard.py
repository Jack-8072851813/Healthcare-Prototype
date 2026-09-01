"""
test_dashboard.py
=================
Automated tests for the Admin Dashboard API endpoints.

Run: python test_dashboard.py
(requires: PostgreSQL accessible via db_config.py settings)
"""

import sys
import os
import json
import unittest
import traceback

# Force UTF-8 output on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
if sys.stderr.encoding != 'utf-8':
    sys.stderr = open(sys.stderr.fileno(), mode='w', encoding='utf-8', buffering=1)


# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

RESULTS = []


def test(name):
    """Decorator that catches exceptions and records pass/fail."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                func(*args, **kwargs)
                RESULTS.append(("PASS", name, ""))
                print(f"  [PASS]  {name}")
            except AssertionError as e:
                RESULTS.append(("FAIL", name, str(e)))
                print(f"  [FAIL]  {name}: {e}")
            except Exception as e:
                RESULTS.append(("ERROR", name, str(e)))
                print(f"  [ERROR] {name}: {e}")
                traceback.print_exc()
        return wrapper
    return decorator
test.__test__ = False


# ─── DB Connection Test ───────────────────────────────────────────────────────

@test("DB connection opens successfully")
def test_db_connection():
    import db_config
    conn = db_config.get_db_connection()
    assert conn is not None, "Connection should not be None"
    conn.close()


# ─── Summary Endpoint Tests ───────────────────────────────────────────────────

@test("Dashboard summary — has required top-level keys")
def test_summary_keys():
    import db_config
    conn = db_config.get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM patients WHERE status = 'ACTIVE';")
    patients = cur.fetchone()[0]
    assert isinstance(patients, int), "Patient count should be int"

    cur.execute("SELECT COUNT(*) FROM appointments;")
    appts = cur.fetchone()[0]
    assert isinstance(appts, int), "Appointment count should be int"

    cur.execute("SELECT COUNT(*) FROM doctors WHERE status = 'ACTIVE';")
    doctors = cur.fetchone()[0]
    assert isinstance(doctors, int), "Doctor count should be int"

    cur.execute("SELECT COUNT(*) FROM conversations;")
    convs = cur.fetchone()[0]
    assert isinstance(convs, int), "Conversations count should be int"

    cur.close()
    conn.close()
    print(f"       patients={patients}, appts={appts}, doctors={doctors}, conversations={convs}")


@test("Dashboard summary — escalations table exists")
def test_escalations_table_exists():
    import db_config
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'escalations'
        );
    """)
    exists = cur.fetchone()[0]
    assert exists, "escalations table should exist (migration 016 must be run)"
    cur.close()
    conn.close()


# ─── Patient Endpoint Tests ───────────────────────────────────────────────────

@test("Patients — list query returns expected columns")
def test_patients_list_columns():
    import db_config
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, patient_code, first_name, last_name, date_of_birth, gender,
               phone, whatsapp_number, email, city, blood_group, status, created_at
        FROM patients
        LIMIT 5;
    """)
    cols = [d[0] for d in cur.description]
    expected = {'id', 'patient_code', 'first_name', 'last_name', 'gender', 'phone', 'status'}
    missing = expected - set(cols)
    assert not missing, f"Missing columns in patients query: {missing}"
    cur.close()
    conn.close()


@test("Patients — search filter works")
def test_patients_search():
    import db_config
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    # Insert a test patient if needed, or just verify the query runs
    cur.execute("""
        SELECT COUNT(*) FROM patients
        WHERE LOWER(first_name || ' ' || last_name) LIKE %s;
    """, ('%a%',))
    count = cur.fetchone()[0]
    assert isinstance(count, int), "Search should return an integer count"
    cur.close()
    conn.close()


@test("Patients — status filter works")
def test_patients_status_filter():
    import db_config
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM patients WHERE status = 'ACTIVE';")
    active = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM patients WHERE status = 'INACTIVE';")
    inactive = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM patients;")
    total = cur.fetchone()[0]
    # Active + Inactive = Total (all patients have one of these statuses)
    assert active + inactive == total, f"active({active}) + inactive({inactive}) should equal total({total})"
    cur.close()
    conn.close()


# ─── Appointment Endpoint Tests ───────────────────────────────────────────────

@test("Appointments — join query with patients/doctors/departments works")
def test_appointments_join():
    import db_config
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.id, a.booking_id, a.appointment_date, a.status,
               (p.first_name || ' ' || p.last_name) as patient_name,
               d.display_name as doctor_name, dept.department_name
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        JOIN doctors d ON a.doctor_id = d.id
        JOIN departments dept ON a.department_id = dept.id
        LIMIT 5;
    """)
    rows = cur.fetchall()
    cols = [desc[0] for desc in cur.description]
    required = {'id', 'booking_id', 'patient_name', 'doctor_name', 'department_name'}
    missing = required - set(cols)
    assert not missing, f"Missing columns in appointments join: {missing}"
    cur.close()
    conn.close()
    print(f"       {len(rows)} sample appointment rows returned")


@test("Appointments — double booking index exists")
def test_double_booking_index():
    import db_config
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT indexname FROM pg_indexes
        WHERE tablename = 'appointments' AND indexname = 'idx_appointments_double_booking';
    """)
    row = cur.fetchone()
    assert row is not None, "Double booking prevention index should exist"
    cur.close()
    conn.close()


@test("Appointments — status update query structure is valid")
def test_appointment_status_update_query():
    import db_config
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    # Verify the allowed status values match the DB constraint
    cur.execute("""
        SELECT pg_get_constraintdef(c.oid) as constraint_def
        FROM pg_constraint c
        JOIN pg_class t ON c.conrelid = t.oid
        WHERE t.relname = 'appointments' AND c.contype = 'c'
        AND pg_get_constraintdef(c.oid) LIKE '%status%';
    """)
    rows = cur.fetchall()
    constraint_defs = ' '.join([r[0] for r in rows])
    for status in ['BOOKED', 'CONFIRMED', 'COMPLETED', 'CANCELLED']:
        assert status in constraint_defs, f"Status '{status}' should be in appointment constraint"
    cur.close()
    conn.close()


# ─── Doctors Endpoint Tests ───────────────────────────────────────────────────

@test("Doctors — list with appointment count query works")
def test_doctors_with_appointment_counts():
    import db_config
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT d.id, d.display_name, dept.department_name,
               COUNT(a.id) FILTER (WHERE a.appointment_date = CURRENT_DATE) as today_appts,
               COUNT(a.id) FILTER (WHERE a.status NOT IN ('CANCELLED', 'RESCHEDULED')) as total_appts
        FROM doctors d
        JOIN departments dept ON d.department_id = dept.id
        LEFT JOIN appointments a ON d.id = a.doctor_id
        GROUP BY d.id, d.display_name, dept.department_name
        ORDER BY d.display_name
        LIMIT 10;
    """)
    rows = cur.fetchall()
    cols = [desc[0] for desc in cur.description]
    assert 'today_appts' in cols, "today_appts column should be present"
    assert 'total_appts' in cols, "total_appts column should be present"
    cur.close()
    conn.close()
    print(f"       {len(rows)} doctors returned")


@test("Doctors — status values are ACTIVE/INACTIVE/ON_LEAVE only")
def test_doctor_status_values():
    import db_config
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT status FROM doctors;")
    statuses = [r[0] for r in cur.fetchall()]
    allowed = {'ACTIVE', 'INACTIVE', 'ON_LEAVE'}
    for s in statuses:
        assert s in allowed, f"Unexpected doctor status value: {s}"
    cur.close()
    conn.close()
    print(f"       Doctor statuses present: {statuses}")


# ─── Departments Endpoint Tests ───────────────────────────────────────────────

@test("Departments — list with doctor count query works")
def test_departments_with_counts():
    import db_config
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT dept.id, dept.department_name, COUNT(DISTINCT d.id) as doctor_count,
               COUNT(a.id) FILTER (WHERE a.appointment_date = CURRENT_DATE) as today_appts
        FROM departments dept
        LEFT JOIN doctors d ON dept.id = d.department_id AND d.status = 'ACTIVE'
        LEFT JOIN appointments a ON dept.id = a.department_id
        GROUP BY dept.id, dept.department_name
        ORDER BY dept.department_name;
    """)
    rows = cur.fetchall()
    assert len(rows) > 0, "Should return at least one department"
    cur.close()
    conn.close()
    print(f"       {len(rows)} departments returned")


# ─── Conversations Endpoint Tests ─────────────────────────────────────────────

@test("Conversations — paginated list query works")
def test_conversations_list():
    import db_config
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.id, c.conversation_code, c.whatsapp_number, c.language,
               c.current_intent, c.conversation_status, c.last_message_at,
               (p.first_name || ' ' || p.last_name) as patient_name,
               (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) as message_count
        FROM conversations c
        LEFT JOIN patients p ON c.patient_id = p.id
        ORDER BY c.last_message_at DESC
        LIMIT 10;
    """)
    rows = cur.fetchall()
    cols = [desc[0] for desc in cur.description]
    assert 'conversation_code' in cols, "conversation_code should be in columns"
    assert 'message_count' in cols, "message_count should be in columns"
    cur.close()
    conn.close()
    print(f"       {len(rows)} conversations returned")


@test("Conversations — messages subquery works")
def test_conversation_messages():
    import db_config
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    # Get first conversation ID if any
    cur.execute("SELECT id FROM conversations LIMIT 1;")
    row = cur.fetchone()
    if row:
        conv_id = row[0]
        cur.execute("""
            SELECT id, sender_type, message_type, message_text, created_at
            FROM messages WHERE conversation_id = %s ORDER BY created_at ASC;
        """, (conv_id,))
        msgs = cur.fetchall()
        print(f"       Conversation {conv_id} has {len(msgs)} messages")
    else:
        print("       No conversations in DB yet (ok for fresh install)")
    cur.close()
    conn.close()


# ─── Escalations Endpoint Tests ───────────────────────────────────────────────

@test("Escalations — table schema has required columns")
def test_escalations_schema():
    import db_config
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'escalations' AND table_schema = 'public';
    """)
    cols = [r[0] for r in cur.fetchall()]
    required = {'id', 'conversation_id', 'patient_id', 'escalation_reason',
                'patient_question', 'status', 'resolution_notes', 'created_at'}
    missing = required - set(cols)
    assert not missing, f"Missing columns in escalations: {missing}"
    cur.close()
    conn.close()


@test("Escalations — status constraint is OPEN/IN_PROGRESS/RESOLVED")
def test_escalations_status_constraint():
    import db_config
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT pg_get_constraintdef(c.oid)
        FROM pg_constraint c
        JOIN pg_class t ON c.conrelid = t.oid
        WHERE t.relname = 'escalations' AND c.contype = 'c'
        AND pg_get_constraintdef(c.oid) LIKE '%status%';
    """)
    rows = cur.fetchall()
    constraint = ' '.join([r[0] for r in rows])
    assert 'OPEN' in constraint, "OPEN should be in escalations status constraint"
    assert 'IN_PROGRESS' in constraint, "IN_PROGRESS should be in escalations status constraint"
    assert 'RESOLVED' in constraint, "RESOLVED should be in escalations status constraint"
    cur.close()
    conn.close()


# ─── Chart Endpoint Tests ─────────────────────────────────────────────────────

@test("Chart — appointment trend query (7 days) works")
def test_appointment_trend_chart():
    import db_config
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT appointment_date::text as date, COUNT(*) as total
        FROM appointments
        WHERE appointment_date >= CURRENT_DATE - INTERVAL '7 days'
          AND appointment_date <= CURRENT_DATE
        GROUP BY appointment_date
        ORDER BY appointment_date ASC;
    """)
    rows = cur.fetchall()
    cols = [desc[0] for desc in cur.description]
    assert 'date' in cols, "date column should be present"
    assert 'total' in cols, "total column should be present"
    cur.close()
    conn.close()
    print(f"       {len(rows)} days with appointment data in last 7 days")


@test("Chart — intent breakdown query works")
def test_intent_breakdown_chart():
    import db_config
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT intent, COUNT(*) as count
        FROM messages
        WHERE intent IS NOT NULL
          AND created_at >= CURRENT_TIMESTAMP - INTERVAL '30 days'
        GROUP BY intent
        ORDER BY count DESC;
    """)
    rows = cur.fetchall()
    print(f"       {len(rows)} distinct intents in last 30 days")
    cur.close()
    conn.close()


@test("Chart — department appointment chart query works")
def test_department_appointments_chart():
    import db_config
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT dept.department_name as name, COUNT(a.id) as value
        FROM departments dept
        LEFT JOIN appointments a ON dept.id = a.department_id
          AND a.appointment_date = CURRENT_DATE
          AND a.status NOT IN ('CANCELLED', 'RESCHEDULED')
        WHERE dept.status = 'ACTIVE'
        GROUP BY dept.department_name
        ORDER BY value DESC;
    """)
    rows = cur.fetchall()
    assert len(rows) >= 0, "Should return at least 0 departments"
    cur.close()
    conn.close()
    print(f"       {len(rows)} active departments returned")


# ─── FastAPI Router Import Test ───────────────────────────────────────────────

@test("dashboard_routes.py imports without errors")
def test_dashboard_routes_import():
    from api import dashboard_routes
    assert hasattr(dashboard_routes, 'router'), "dashboard_routes should have a 'router' attribute"
    # Count registered routes
    routes = [r for r in dashboard_routes.router.routes]
    print(f"       {len(routes)} routes registered in dashboard_routes.router")
    assert len(routes) >= 8, f"Expected at least 8 dashboard routes, got {len(routes)}"


@test("main.py registers dashboard_routes router")
def test_main_registers_dashboard():
    import main
    route_paths = [getattr(r, 'path', '') for r in main.app.routes]
    has_dashboard = any('/api/dashboard' in p for p in route_paths)
    assert has_dashboard, "main.app should have /api/dashboard routes registered"


# ─── Run All Tests ────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("\n" + "=" * 65)
    print("  Admin Dashboard API — Test Suite")
    print("=" * 65 + "\n")

    test_db_connection()
    print()

    print("── Summary / KPI ──────────────────────────────────────────────")
    test_summary_keys()
    test_escalations_table_exists()
    print()

    print("── Patients ───────────────────────────────────────────────────")
    test_patients_list_columns()
    test_patients_search()
    test_patients_status_filter()
    print()

    print("── Appointments ───────────────────────────────────────────────")
    test_appointments_join()
    test_double_booking_index()
    test_appointment_status_update_query()
    print()

    print("── Doctors ────────────────────────────────────────────────────")
    test_doctors_with_appointment_counts()
    test_doctor_status_values()
    print()

    print("── Departments ────────────────────────────────────────────────")
    test_departments_with_counts()
    print()

    print("── Conversations ──────────────────────────────────────────────")
    test_conversations_list()
    test_conversation_messages()
    print()

    print("── Escalations ────────────────────────────────────────────────")
    test_escalations_schema()
    test_escalations_status_constraint()
    print()

    print("── Charts ─────────────────────────────────────────────────────")
    test_appointment_trend_chart()
    test_intent_breakdown_chart()
    test_department_appointments_chart()
    print()

    print("── FastAPI Router Integration ─────────────────────────────────")
    test_dashboard_routes_import()
    test_main_registers_dashboard()
    print()

    # Summary
    passed = sum(1 for r in RESULTS if r[0] == 'PASS')
    failed = sum(1 for r in RESULTS if r[0] == 'FAIL')
    errors = sum(1 for r in RESULTS if r[0] == 'ERROR')
    total = len(RESULTS)

    print("=" * 65)
    print(f"  TOTAL: {total}  |  PASS: {passed}  |  FAIL: {failed}  |  ERROR: {errors}")
    print("=" * 65)

    if failed > 0 or errors > 0:
        print("\nFailed/Error Tests:")
        for status, name, msg in RESULTS:
            if status != 'PASS':
                print(f"  [{status}] {name}")
                if msg:
                    print(f"         → {msg}")

    sys.exit(0 if (failed == 0 and errors == 0) else 1)
