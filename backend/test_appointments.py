import datetime
import threading
import time
import json
import psycopg2
import db_config
import appointment_service

def setup_test_ids():
    """Fetches valid IDs from the seeded database for patient, doctor, department, admin, and doctor user."""
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        # Get patient
        cur.execute("SELECT id FROM patients WHERE patient_code = 'P001';")
        patient_id = cur.fetchone()[0]
        
        # Get doctor
        cur.execute("SELECT id, department_id FROM doctors WHERE doctor_code = 'DR001';")
        row = cur.fetchone()
        doctor_id = row[0]
        department_id = row[1]
        
        # Get another patient
        cur.execute("SELECT id FROM patients WHERE patient_code = 'P002';")
        other_patient_id = cur.fetchone()[0]
        
        # Get another doctor
        cur.execute("SELECT id, department_id FROM doctors WHERE doctor_code = 'DR002';")
        row2 = cur.fetchone()
        other_doctor_id = row2[0]
        other_department_id = row2[1]
        
        # Get users
        cur.execute("SELECT id FROM users WHERE username = 'admin';")
        admin_user_id = cur.fetchone()[0]
        
        cur.execute("SELECT id FROM users WHERE username = 'doc1';")
        doc_user_id = cur.fetchone()[0]
        
        return {
            "patient_id": patient_id,
            "other_patient_id": other_patient_id,
            "doctor_id": doctor_id,
            "other_doctor_id": other_doctor_id,
            "department_id": department_id,
            "other_department_id": other_department_id,
            "admin_user_id": admin_user_id,
            "doc_user_id": doc_user_id
        }
    finally:
        cur.close()
        conn.close()

def cleanup_test_appointments():
    """Removes all test appointments, audit logs, and notifications starting with 'TEST_BK_' or on test dates."""
    import datetime
    today = datetime.date.today()
    days_ahead = 7 - today.weekday() # Next Monday
    if days_ahead <= 0:
        days_ahead += 7
    test_date = (today + datetime.timedelta(days=days_ahead + 7)).strftime("%Y-%m-%d")
    
    days_to_tuesday = (1 - today.weekday()) % 7
    if days_to_tuesday <= 0:
        days_to_tuesday += 7
    tuesday_date = (today + datetime.timedelta(days=days_to_tuesday + 7)).strftime("%Y-%m-%d")

    conn = db_config.get_db_connection()
    conn.autocommit = True
    cur = conn.cursor()
    try:
        # Fetch IDs first to delete child records properly
        cur.execute("SELECT id FROM appointments WHERE booking_id LIKE 'TEST_BK%%' OR appointment_date IN (%s, %s);", (test_date, tuesday_date))
        appt_ids = [row[0] for row in cur.fetchall()]
        
        if appt_ids:
            appt_ids_str = ",".join(str(i) for i in appt_ids)
            # Delete notifications
            cur.execute(f"DELETE FROM notifications WHERE appointment_id IN ({appt_ids_str});")
            # Delete audit logs
            cur.execute(f"DELETE FROM audit_logs WHERE entity_type = 'appointments' AND entity_id IN ({appt_ids_str});")
            # Delete appointments
            cur.execute(f"DELETE FROM appointments WHERE id IN ({appt_ids_str});")
        print("Test database environment cleaned up.")
    finally:
        cur.close()
        conn.close()

def run_tests():
    ids = setup_test_ids()
    cleanup_test_appointments()
    
    # We will pick a Monday 2 weeks in the future to ensure we don't overlap with seeded appointments
    today = datetime.date.today()
    days_ahead = 7 - today.weekday() # Next Monday
    if days_ahead <= 0:
        days_ahead += 7
    test_date = (today + datetime.timedelta(days=days_ahead + 7)).strftime("%Y-%m-%d")
    
    # Dr. Priya is scheduled Tue, Thu
    days_to_tuesday = (1 - today.weekday()) % 7
    if days_to_tuesday <= 0:
        days_to_tuesday += 7
    tuesday_date = (today + datetime.timedelta(days=days_to_tuesday + 7)).strftime("%Y-%m-%d")
    
    print(f"Test Date (Monday): {test_date}")
    print(f"Tuesday Date (for Dr. Priya): {tuesday_date}")
    
    passed_tests = []
    failed_tests = []
    
    def log_result(name, passed, detail=""):
        if passed:
            print(f"[PASS] {name}")
            passed_tests.append(name)
        else:
            print(f"[FAIL] {name} - {detail}")
            failed_tests.append((name, detail))

    # --- TEST 1: Doctor availability ---
    try:
        res = appointment_service.get_doctor_availability(ids["doctor_id"], test_date)
        log_result("TEST 1: Doctor availability", res["available"] == True)
    except Exception as e:
        log_result("TEST 1: Doctor availability", False, str(e))

    # --- TEST 2: Generate available slots ---
    try:
        slots = appointment_service.get_available_slots(ids["doctor_id"], test_date)
        log_result("TEST 2: Generate available slots", len(slots) > 0 and "09:00" in slots)
    except Exception as e:
        log_result("TEST 2: Generate available slots", False, str(e))

    # --- TEST 3: Successful appointment booking ---
    try:
        res = appointment_service.book_appointment(
            patient_id=ids["patient_id"],
            doctor_id=ids["doctor_id"],
            department_id=ids["department_id"],
            date_str=test_date,
            time_str="09:00",
            patient_reason="Regular Checkup",
            booking_source="ADMIN",
            created_by_user_id=ids["admin_user_id"]
        )
        log_result("TEST 3: Successful appointment booking", res["success"] is True and res["booking_id"].startswith("APT"))
    except Exception as e:
        log_result("TEST 3: Successful appointment booking", False, str(e))

    # --- TEST 4: Booking with invalid patient ---
    try:
        appointment_service.book_appointment(
            patient_id=999999, # Invalid patient
            doctor_id=ids["doctor_id"],
            department_id=ids["department_id"],
            date_str=test_date,
            time_str="09:30"
        )
        log_result("TEST 4: Booking with invalid patient", False, "Expected EntityNotFoundError")
    except appointment_service.EntityNotFoundError as e:
        log_result("TEST 4: Booking with invalid patient", e.error_code == "PATIENT_NOT_FOUND")
    except Exception as e:
        log_result("TEST 4: Booking with invalid patient", False, f"Incorrect exception: {e}")

    # --- TEST 5: Booking with invalid doctor ---
    try:
        appointment_service.book_appointment(
            patient_id=ids["patient_id"],
            doctor_id=999999, # Invalid doctor
            department_id=ids["department_id"],
            date_str=test_date,
            time_str="09:30"
        )
        log_result("TEST 5: Booking with invalid doctor", False, "Expected EntityNotFoundError")
    except appointment_service.EntityNotFoundError as e:
        log_result("TEST 5: Booking with invalid doctor", e.error_code == "DOCTOR_NOT_FOUND")
    except Exception as e:
        log_result("TEST 5: Booking with invalid doctor", False, f"Incorrect exception: {e}")

    # --- TEST 6: Booking outside doctor schedule ---
    try:
        appointment_service.book_appointment(
            patient_id=ids["patient_id"],
            doctor_id=ids["doctor_id"],
            department_id=ids["department_id"],
            date_str=test_date,
            time_str="22:00" # Outside schedule (working hours 09:00 - 13:00)
        )
        log_result("TEST 6: Booking outside doctor schedule", False, "Expected InvalidScheduleError")
    except appointment_service.InvalidScheduleError as e:
        log_result("TEST 6: Booking outside doctor schedule", e.error_code == "INVALID_APPOINTMENT_SLOT")
    except Exception as e:
        log_result("TEST 6: Booking outside doctor schedule", False, f"Incorrect exception: {e}")

    # --- TEST 7: Booking in the past ---
    try:
        appointment_service.book_appointment(
            patient_id=ids["patient_id"],
            doctor_id=ids["doctor_id"],
            department_id=ids["department_id"],
            date_str="2020-01-01",
            time_str="10:00"
        )
        log_result("TEST 7: Booking in the past", False, "Expected PastDateError")
    except appointment_service.PastDateError as e:
        log_result("TEST 7: Booking in the past", e.error_code == "APPOINTMENT_DATE_PAST")
    except Exception as e:
        log_result("TEST 7: Booking in the past", False, f"Incorrect exception: {e}")

    # --- TEST 8: Duplicate booking for same doctor/date/time ---
    try:
        # First booking already done in TEST 3 for test_date at 09:00
        # Try to book same doctor/date/time for other patient
        appointment_service.book_appointment(
            patient_id=ids["other_patient_id"],
            doctor_id=ids["doctor_id"],
            department_id=ids["department_id"],
            date_str=test_date,
            time_str="09:00"
        )
        log_result("TEST 8: Duplicate booking for same doctor/date/time", False, "Expected SlotUnavailableError")
    except appointment_service.SlotUnavailableError as e:
        log_result("TEST 8: Duplicate booking for same doctor/date/time", e.error_code == "APPOINTMENT_SLOT_UNAVAILABLE")
    except Exception as e:
        log_result("TEST 8: Duplicate booking for same doctor/date/time", False, f"Incorrect exception: {e}")

    # --- TEST 9: Concurrent duplicate booking ---
    # Setup: We will try to book at 09:30 on test_date concurrently.
    concurrency_results = []
    
    def book_concurrently(thread_id, patient_id):
        try:
            res = appointment_service.book_appointment(
                patient_id=patient_id,
                doctor_id=ids["doctor_id"],
                department_id=ids["department_id"],
                date_str=test_date,
                time_str="09:30",
                booking_source="WHATSAPP_TEXT"
            )
            concurrency_results.append((thread_id, "SUCCESS", res))
        except appointment_service.SlotUnavailableError as e:
            concurrency_results.append((thread_id, "UNAVAILABLE", e.message))
        except Exception as e:
            concurrency_results.append((thread_id, "ERROR", str(e)))

    t1 = threading.Thread(target=book_concurrently, args=(1, ids["patient_id"]))
    t2 = threading.Thread(target=book_concurrently, args=(2, ids["other_patient_id"]))
    
    t1.start()
    t2.start()
    
    t1.join()
    t2.join()
    
    success_count = sum(1 for r in concurrency_results if r[1] == "SUCCESS")
    unavail_count = sum(1 for r in concurrency_results if r[1] == "UNAVAILABLE")
    
    log_result("TEST 9: Concurrent duplicate booking", success_count == 1 and unavail_count == 1, f"Results: {concurrency_results}")

    # Let's fetch the booking ID of the successful appointment from TEST 3 (09:00 slot) for cancellation tests
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT booking_id FROM appointments WHERE doctor_id = %s AND appointment_date = %s AND appointment_time = '09:00:00' AND status = 'BOOKED';", (ids["doctor_id"], test_date))
    booking_id_0900 = cur.fetchone()[0]
    cur.close()
    conn.close()

    # --- TEST 10: Cancellation with reason ---
    try:
        res = appointment_service.cancel_appointment(
            booking_id=booking_id_0900,
            reason="Doctor is unavailable due to emergency conference",
            cancelled_by_user_id=ids["admin_user_id"]
        )
        log_result("TEST 10: Cancellation with reason", res["success"] is True and res["status"] == "CANCELLED")
    except Exception as e:
        log_result("TEST 10: Cancellation with reason", False, str(e))

    # --- TEST 11: Cancellation without reason ---
    try:
        appointment_service.cancel_appointment(
            booking_id=booking_id_0900,
            reason="", # Empty reason
            cancelled_by_user_id=ids["admin_user_id"]
        )
        log_result("TEST 11: Cancellation without reason", False, "Expected AppointmentError")
    except appointment_service.AppointmentError as e:
        log_result("TEST 11: Cancellation without reason", e.error_code == "CANCELLATION_REASON_REQUIRED")
    except Exception as e:
        log_result("TEST 11: Cancellation without reason", False, f"Incorrect exception: {e}")

    # --- TEST 12: Cancelled slot becomes available ---
    try:
        # Since the 09:00 slot was cancelled in TEST 10, booking for this slot should succeed now!
        res = appointment_service.book_appointment(
            patient_id=ids["other_patient_id"],
            doctor_id=ids["doctor_id"],
            department_id=ids["department_id"],
            date_str=test_date,
            time_str="09:00",
            booking_source="WHATSAPP_TEXT"
        )
        log_result("TEST 12: Cancelled slot becomes available", res["success"] is True and res["status"] == "BOOKED")
        booking_id_new_0900 = res["booking_id"]
    except Exception as e:
        log_result("TEST 12: Cancelled slot becomes available", False, str(e))

    # --- TEST 13: Successful rescheduling ---
    try:
        # Reschedule `booking_id_new_0900` from 09:00 to 11:00 on the same date
        res = appointment_service.reschedule_appointment(
            booking_id=booking_id_new_0900,
            new_date_str=test_date,
            new_time_str="11:00",
            reason="Patient requested a different time",
            rescheduled_by_user_id=ids["admin_user_id"]
        )
        log_result("TEST 13: Successful rescheduling", res["success"] is True and res["status"] == "RESCHEDULED" and res["new_time"] == "11:00")
    except Exception as e:
        log_result("TEST 13: Successful rescheduling", False, str(e))

    # --- TEST 14: Rescheduling to occupied slot ---
    try:
        # The 09:30 slot is occupied (booked in TEST 9)
        # Attempting to reschedule `booking_id_new_0900` (now at 11:00) to 09:30 should fail
        appointment_service.reschedule_appointment(
            booking_id=booking_id_new_0900,
            new_date_str=test_date,
            new_time_str="09:30",
            reason="Patient needs early slots",
            rescheduled_by_user_id=ids["admin_user_id"]
        )
        log_result("TEST 14: Rescheduling to occupied slot", False, "Expected SlotUnavailableError")
    except appointment_service.SlotUnavailableError as e:
        log_result("TEST 14: Rescheduling to occupied slot", e.error_code == "APPOINTMENT_SLOT_UNAVAILABLE")
    except Exception as e:
        log_result("TEST 14: Rescheduling to occupied slot", False, f"Incorrect exception: {e}")

    # --- TEST 15: Rescheduling without reason ---
    try:
        appointment_service.reschedule_appointment(
            booking_id=booking_id_new_0900,
            new_date_str=test_date,
            new_time_str="12:00",
            reason="", # Empty reason
            rescheduled_by_user_id=ids["admin_user_id"]
        )
        log_result("TEST 15: Rescheduling without reason", False, "Expected AppointmentError")
    except appointment_service.AppointmentError as e:
        log_result("TEST 15: Rescheduling without reason", e.error_code == "RESCHEDULE_REASON_REQUIRED")
    except Exception as e:
        log_result("TEST 15: Rescheduling without reason", False, f"Incorrect exception: {e}")

    # --- TEST 16: Appointment status lookup ---
    try:
        res = appointment_service.get_appointment(booking_id_new_0900)
        log_result("TEST 16: Appointment status lookup", res["booking_id"] == booking_id_new_0900 and res["appointment_time"] == "11:00")
    except Exception as e:
        log_result("TEST 16: Appointment status lookup", False, str(e))

    # --- TEST 17: Notification record created after cancellation ---
    try:
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT n.notification_type, n.status, n.message 
            FROM notifications n
            JOIN appointments a ON n.appointment_id = a.id
            WHERE a.booking_id = %s AND n.notification_type = 'APPOINTMENT_CANCELLED';
        """, (booking_id_0900,))
        row = cur.fetchone()
        log_result("TEST 17: Notification record created after cancellation", row is not None and row[1] == 'PENDING' and "cancelled because" in row[2])
        cur.close()
        conn.close()
    except Exception as e:
        log_result("TEST 17: Notification record created after cancellation", False, str(e))

    # --- TEST 18: Notification record created after rescheduling ---
    try:
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT n.notification_type, n.status, n.message 
            FROM notifications n
            JOIN appointments a ON n.appointment_id = a.id
            WHERE a.booking_id = %s AND n.notification_type = 'APPOINTMENT_RESCHEDULED';
        """, (booking_id_new_0900,))
        row = cur.fetchone()
        log_result("TEST 18: Notification record created after rescheduling", row is not None and row[1] == 'PENDING' and "rescheduled to" in row[2])
        cur.close()
        conn.close()
    except Exception as e:
        log_result("TEST 18: Notification record created after rescheduling", False, str(e))

    # --- TEST 19: Audit log created for Admin cancellation ---
    try:
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT action, user_id FROM audit_logs
            WHERE action = 'CANCEL_APPOINTMENT' AND user_id = %s;
        """, (ids["admin_user_id"],))
        row = cur.fetchone()
        log_result("TEST 19: Audit log created for Admin cancellation", row is not None)
        cur.close()
        conn.close()
    except Exception as e:
        log_result("TEST 19: Audit log created for Admin cancellation", False, str(e))

    # --- TEST 20: Audit log created for Doctor rescheduling ---
    # To test this, let's reschedule using doc_user_id
    try:
        # Reschedule from 11:00 to 12:00
        appointment_service.reschedule_appointment(
            booking_id=booking_id_new_0900,
            new_date_str=test_date,
            new_time_str="12:00",
            reason="Rescheduled by Doctor",
            rescheduled_by_user_id=ids["doc_user_id"]
        )
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT action, user_id FROM audit_logs
            WHERE action = 'RESCHEDULE_APPOINTMENT' AND user_id = %s;
        """, (ids["doc_user_id"],))
        row = cur.fetchone()
        log_result("TEST 20: Audit log created for Doctor rescheduling", row is not None)
        cur.close()
        conn.close()
    except Exception as e:
        log_result("TEST 20: Audit log created for Doctor rescheduling", False, str(e))

    print("\n=== SUMMARY OF TESTS ===")
    print(f"Passed: {len(passed_tests)}/20")
    print(f"Failed: {len(failed_tests)}/20")
    
    if failed_tests:
        print("\n--- Failures ---")
        for name, err in failed_tests:
            print(f"- {name}: {err}")
        return False
    return True

if __name__ == "__main__":
    try:
        success = run_tests()
        # Clean up test database records
        cleanup_test_appointments()
        if not success:
            exit(1)
        print("\nAll verifications passed! Exiting successfully.")
        exit(0)
    except Exception as ex:
        print(f"Fatal error during tests: {ex}")
        cleanup_test_appointments()
        exit(1)
