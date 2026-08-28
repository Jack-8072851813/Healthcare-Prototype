import datetime
import bcrypt
import psycopg2
import db_config

def test_verify_schema(cur):
    """Verify that all 15 tables exist in the public schema."""
    print("\n--- Test 1: Verifying Schema Table Presence ---")
    required_tables = [
        "roles", "users", "patients", "departments", "doctors", 
        "doctor_schedules", "appointments", "pre_admissions", 
        "conversations", "messages", "notifications", "audit_logs", 
        "knowledge_documents", "knowledge_chunks", "agent_action_logs"
    ]
    
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public';
    """)
    existing_tables = {t[0] for t in cur.fetchall()}
    
    all_passed = True
    for table in required_tables:
        if table in existing_tables:
            print(f"[PASS] Table '{table}' exists.")
        else:
            print(f"[FAIL] Table '{table}' is MISSING.")
            all_passed = False
            
    assert all_passed, "Schema verification failed: some tables are missing!"
    print("Schema verification passed successfully!")

def test_verify_seeds(cur):
    """Verify seed counts and login credentials."""
    print("\n--- Test 2: Verifying Seed Data Counts & Logins ---")
    
    # 1. Check counts
    cur.execute("SELECT COUNT(*) FROM roles;")
    roles_cnt = cur.fetchone()[0]
    print(f"Roles count: {roles_cnt} (Required: 2)")
    assert roles_cnt >= 2
    
    cur.execute("SELECT COUNT(*) FROM users;")
    users_cnt = cur.fetchone()[0]
    print(f"Users count: {users_cnt} (Required: >= 3)")
    assert users_cnt >= 3
    
    cur.execute("SELECT COUNT(*) FROM departments;")
    dept_cnt = cur.fetchone()[0]
    print(f"Departments count: {dept_cnt} (Required: 8)")
    assert dept_cnt == 8
    
    cur.execute("SELECT COUNT(*) FROM doctors;")
    doc_cnt = cur.fetchone()[0]
    print(f"Doctors count: {doc_cnt} (Required: 2)")
    assert doc_cnt >= 2
    
    cur.execute("SELECT COUNT(*) FROM patients;")
    patient_cnt = cur.fetchone()[0]
    print(f"Patients count: {patient_cnt} (Required: 10)")
    assert patient_cnt >= 10
    
    cur.execute("SELECT COUNT(*) FROM appointments;")
    appt_cnt = cur.fetchone()[0]
    print(f"Appointments count: {appt_cnt} (Required: >= 10)")
    assert appt_cnt >= 10
    
    cur.execute("SELECT COUNT(*) FROM pre_admissions;")
    pa_cnt = cur.fetchone()[0]
    print(f"Pre-admissions count: {pa_cnt} (Required: >= 3)")
    assert pa_cnt >= 3

    # 2. Check credentials & password hashing (admin, doc1, doc2)
    users_to_check = [("admin", "admin"), ("doc1", "doc1"), ("doc2", "doc2")]
    for username, plain_password in users_to_check:
        cur.execute("SELECT password_hash, is_active FROM users WHERE username = %s;", (username,))
        row = cur.fetchone()
        assert row is not None, f"User '{username}' is missing!"
        pwd_hash, is_active = row
        
        # Ensure password is NOT plaintext
        assert pwd_hash != plain_password, f"Password for '{username}' is stored as plaintext!"
        
        # Verify hash match
        is_match = bcrypt.checkpw(plain_password.encode('utf-8'), pwd_hash.encode('utf-8'))
        assert is_match, f"Password check failed for '{username}'!"
        assert is_active, f"User '{username}' is inactive!"
        print(f"[PASS] Verified user '{username}' exists with hashed password and is active.")
        
    print("Seed data verification passed successfully!")

def test_verify_relationships(cur):
    """Verify that patient, doctor, and department relationships work via joins."""
    print("\n--- Test 3: Verifying Relationships and Joins ---")
    
    cur.execute("""
        SELECT 
            a.booking_id,
            p.first_name || ' ' || p.last_name AS patient_name,
            d.display_name AS doctor_name,
            dept.department_name,
            a.appointment_date,
            a.appointment_time,
            a.status
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        JOIN doctors d ON a.doctor_id = d.id
        JOIN departments dept ON a.department_id = dept.id
        LIMIT 5;
    """)
    rows = cur.fetchall()
    assert len(rows) > 0, "No appointments found to verify relationships!"
    
    for row in rows:
        print(f"Appointment {row[0]}: Patient '{row[1]}' is seeing Doctor '{row[2]}' in '{row[3]}' on {row[4]} at {row[5]} [{row[6]}]")
        
    print("[PASS] Relationships and joins validated successfully.")

def test_double_booking_prevention(conn):
    """Verify the database-level double-booking prevention rule."""
    print("\n--- Test 4: Testing Double-Booking Prevention Rule ---")
    cur = conn.cursor()
    
    # Let's clean up test data from previous runs if any
    cur.execute("DELETE FROM appointments WHERE booking_id LIKE 'TEST_BK%';")
    conn.commit()
    
    # Get active doctor, patient, and department
    cur.execute("SELECT id FROM doctors LIMIT 1;")
    doctor_id = cur.fetchone()[0]
    cur.execute("SELECT id FROM patients LIMIT 2;")
    patient_id_1 = cur.fetchone()[0]
    patient_id_2 = cur.fetchall()[0][0] # Fetch second patient
    cur.execute("SELECT id FROM departments LIMIT 1;")
    department_id = cur.fetchone()[0]
    
    test_date = datetime.date.today() + datetime.timedelta(days=10)
    test_time = datetime.time(10, 0, 0)
    
    print(f"Attempting to book Patient 1 with Doctor ID {doctor_id} on {test_date} at {test_time} (Booking ID: TEST_BK001)...")
    
    try:
        # First booking should succeed
        cur.execute("""
            INSERT INTO appointments (booking_id, patient_id, doctor_id, department_id, appointment_date, appointment_time, status, booking_source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
        """, ("TEST_BK001", patient_id_1, doctor_id, department_id, test_date, test_time, "BOOKED", "ADMIN"))
        conn.commit()
        print("[PASS] Patient 1 appointment booked successfully.")
        
        # Second booking for the same slot (Active status: CONFIRMED) should FAIL
        print(f"Attempting to book Patient 2 with Doctor ID {doctor_id} on {test_date} at {test_time} (Booking ID: TEST_BK002, Status: CONFIRMED)...")
        try:
            cur.execute("""
                INSERT INTO appointments (booking_id, patient_id, doctor_id, department_id, appointment_date, appointment_time, status, booking_source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
            """, ("TEST_BK002", patient_id_2, doctor_id, department_id, test_date, test_time, "CONFIRMED", "ADMIN"))
            conn.commit()
            print("[FAIL] Encountered unexpected success! Enforce rule failed.")
            assert False, "Double booking succeeded but should have failed!"
        except psycopg2.errors.UniqueViolation as e:
            conn.rollback()
            print(f"[PASS] Successfully rejected double-booking. PostgreSQL error: {e.pgerror.strip()}")
            
        # Third booking (In-active status: CANCELLED) for the same slot should SUCCEED
        print(f"Attempting to book Patient 2 with Doctor ID {doctor_id} on {test_date} at {test_time} (Booking ID: TEST_BK003, Status: CANCELLED)...")
        try:
            cur.execute("""
                INSERT INTO appointments (booking_id, patient_id, doctor_id, department_id, appointment_date, appointment_time, status, booking_source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
            """, ("TEST_BK003", patient_id_2, doctor_id, department_id, test_date, test_time, "CANCELLED", "ADMIN"))
            conn.commit()
            print("[PASS] Cancelled appointment successfully inserted for the same slot without blocking.")
        except Exception as e:
            conn.rollback()
            print(f"[FAIL] Failed to insert CANCELLED appointment: {e}")
            raise e
            
        # Fourth booking (In-active status: RESCHEDULED) for the same slot should SUCCEED
        print(f"Attempting to book Patient 2 with Doctor ID {doctor_id} on {test_date} at {test_time} (Booking ID: TEST_BK004, Status: RESCHEDULED)...")
        try:
            cur.execute("""
                INSERT INTO appointments (booking_id, patient_id, doctor_id, department_id, appointment_date, appointment_time, status, booking_source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
            """, ("TEST_BK004", patient_id_2, doctor_id, department_id, test_date, test_time, "RESCHEDULED", "ADMIN"))
            conn.commit()
            print("[PASS] Rescheduled appointment successfully inserted for the same slot without blocking.")
        except Exception as e:
            conn.rollback()
            print(f"[FAIL] Failed to insert RESCHEDULED appointment: {e}")
            raise e
            
        # Clean up test records
        cur.execute("DELETE FROM appointments WHERE booking_id LIKE 'TEST_BK%';")
        conn.commit()
        print("Double-booking verification cleanup finished successfully.")
        
    except Exception as e:
        conn.rollback()
        # Clean up in case of failure
        cur.execute("DELETE FROM appointments WHERE booking_id LIKE 'TEST_BK%';")
        conn.commit()
        print(f"Error during double booking test: {e}")
        raise e
    finally:
        cur.close()

def main():
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        test_verify_schema(cur)
        test_verify_seeds(cur)
        test_verify_relationships(cur)
        test_double_booking_prevention(conn)
        print("\n=============================================")
        print("ALL VERIFICATIONS PASSED SUCCESSFULLY!")
        print("=============================================")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()
