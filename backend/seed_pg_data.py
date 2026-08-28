import datetime
import json
import random
import bcrypt
import psycopg2
import db_config

def get_hashed_password(plain_text_password: str) -> str:
    """Hashes a password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain_text_password.encode('utf-8'), salt).decode('utf-8')

def get_mock_vector(dim=1536):
    """Generates a mock vector of specified dimension."""
    # Let's populate first 5 elements with small random values, rest as 0.0 to keep it clean
    vec = [round(random.uniform(-0.1, 0.1), 6) for _ in range(5)] + [0.0] * (dim - 5)
    return vec

def seed_data():
    conn = db_config.get_db_connection()
    conn.autocommit = False
    cur = conn.cursor()
    
    try:
        print("Starting database seeding...")
        
        # 1. Fetch Roles IDs
        cur.execute("SELECT id, name FROM roles;")
        roles_dict = {name: r_id for r_id, name in cur.fetchall()}
        admin_role_id = roles_dict['ADMIN']
        doctor_role_id = roles_dict['DOCTOR']
        
        # 2. Insert Users (Admin, doc1, doc2)
        print("Seeding Users...")
        users_data = [
            ("admin", "admin@meridian.com", get_hashed_password("admin"), admin_role_id, "System", "Admin", "9999999999", True, False),
            ("doc1", "arun.kumar@meridian.com", get_hashed_password("doc1"), doctor_role_id, "Arun", "Kumar", "9888888881", True, False),
            ("doc2", "priya.ramesh@meridian.com", get_hashed_password("doc2"), doctor_role_id, "Priya", "Ramesh", "9888888882", True, False)
        ]
        
        user_ids = {}
        for username, email, pwd_hash, r_id, fname, lname, phone, is_act, must_change in users_data:
            cur.execute("""
                INSERT INTO users (username, email, password_hash, role_id, first_name, last_name, phone, is_active, must_change_password)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (username) DO UPDATE 
                SET email = EXCLUDED.email, password_hash = EXCLUDED.password_hash, is_active = EXCLUDED.is_active
                RETURNING id;
            """, (username, email, pwd_hash, r_id, fname, lname, phone, is_act, must_change))
            user_ids[username] = cur.fetchone()[0]
            
        # 3. Insert Departments
        print("Seeding Departments...")
        departments_data = [
            ("D001", "General Medicine", "Outpatient and inpatient medical care for general ailments"),
            ("D002", "Cardiology", "Heart health, diagnostics, and cardiovascular treatments"),
            ("D003", "Pediatrics", "Specialized medical care for infants, children, and adolescents"),
            ("D004", "Orthopedics", "Bone, joint, ligament, and musculoskeletal treatments"),
            ("D005", "Dermatology", "Skin, hair, nail treatments and cosmetic consultations"),
            ("D006", "ENT", "Ear, Nose, and Throat diagnostics and procedures"),
            ("D007", "Gynecology", "Women health, prenatal care, and obstetric services"),
            ("D008", "Neurology", "Brain, spinal cord, and nervous system medical management")
        ]
        
        dept_ids = {}
        for code, name, desc in departments_data:
            cur.execute("""
                INSERT INTO departments (department_code, department_name, description, status)
                VALUES (%s, %s, %s, 'ACTIVE')
                ON CONFLICT (department_code) DO UPDATE
                SET department_name = EXCLUDED.department_name, description = EXCLUDED.description
                RETURNING id;
            """, (code, name, desc))
            dept_ids[code] = cur.fetchone()[0]
            
        # 4. Insert Doctors Profiles
        print("Seeding Doctors Profiles...")
        doctors_data = [
            ("DR001", user_ids["doc1"], dept_ids["D001"], "Arun", "Kumar", "Dr. Arun Kumar", "General Medicine", "MBBS, MD", 12, "9888888881", "arun.kumar@meridian.com", 500.00),
            ("DR002", user_ids["doc2"], dept_ids["D002"], "Priya", "Ramesh", "Dr. Priya Ramesh", "Cardiology", "MBBS, MD, DM (Cardiology)", 15, "9888888882", "priya.ramesh@meridian.com", 800.00)
        ]
        
        doc_ids = {}
        for code, u_id, d_id, fname, lname, display, spec, qual, exp, phone, email, fee in doctors_data:
            cur.execute("""
                INSERT INTO doctors (doctor_code, user_id, department_id, first_name, last_name, display_name, specialization, qualification, experience_years, phone, email, consultation_fee, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'ACTIVE')
                ON CONFLICT (doctor_code) DO UPDATE
                SET department_id = EXCLUDED.department_id, display_name = EXCLUDED.display_name, consultation_fee = EXCLUDED.consultation_fee
                RETURNING id;
            """, (code, u_id, d_id, fname, lname, display, spec, qual, exp, phone, email, fee))
            doc_ids[code] = cur.fetchone()[0]
            
        # 5. Insert Doctor Schedules
        print("Seeding Doctor Schedules...")
        schedules_data = [
            # Dr. Arun Kumar - Mon, Wed, Fri (9:00 - 13:00)
            (doc_ids["DR001"], "MONDAY", "09:00:00", "13:00:00", 30),
            (doc_ids["DR001"], "WEDNESDAY", "09:00:00", "13:00:00", 30),
            (doc_ids["DR001"], "FRIDAY", "09:00:00", "13:00:00", 30),
            # Dr. Priya Ramesh - Tue, Thu (14:00 - 18:00)
            (doc_ids["DR002"], "TUESDAY", "14:00:00", "18:00:00", 30),
            (doc_ids["DR002"], "THURSDAY", "14:00:00", "18:00:00", 30),
        ]
        
        for d_id, day, start, end, slot_dur in schedules_data:
            cur.execute("""
                INSERT INTO doctor_schedules (doctor_id, day_of_week, start_time, end_time, slot_duration_minutes, effective_from, status)
                VALUES (%s, %s, %s, %s, %s, CURRENT_DATE - 30, 'ACTIVE');
            """, (d_id, day, start, end, slot_dur))
            
        # 6. Insert Patients (10 realistic sample patients)
        print("Seeding Patients...")
        patients_data = [
            ("P001", "Ramesh", "Kumar", "1978-04-12", "MALE", "9876543210", "9876543210", "ramesh.k@example.com", "12, Mount Road", "Chennai", "Tamil Nadu", "600002", "Geetha Kumar", "9876543211", "O+"),
            ("P002", "Anitha", "Nair", "1985-08-22", "FEMALE", "8765432109", "8765432109", "anitha.nair@example.com", "45, G.N. Chetty Road", "Chennai", "Tamil Nadu", "600017", "Radhakrishnan Nair", "8765432110", "A+"),
            ("P003", "Karthik", "Selvam", "1990-11-05", "MALE", "7654321098", "7654321098", "karthik.selvam@example.com", "78, ECR Road", "Chennai", "Tamil Nadu", "600041", "Selvamani P", "7654321099", "B+"),
            ("P004", "Meena", "Krishnan", "1963-03-30", "FEMALE", "6543210987", "6543210987", "meena.k@example.com", "102, Anna Nagar", "Chennai", "Tamil Nadu", "600040", "Krishnan R", "6543210988", "O-"),
            ("P005", "Suresh", "Babu", "1982-12-15", "MALE", "9840123456", "9840123456", "suresh.babu@example.com", "5, T. Nagar", "Chennai", "Tamil Nadu", "600017", "Rekha Babu", "9840123457", "AB+"),
            ("P006", "Lakshmi", "Devi", "1975-07-18", "FEMALE", "9840654321", "9840654321", "lakshmi.d@example.com", "14, Velachery Bypass", "Chennai", "Tamil Nadu", "600042", "Venkatraman S", "9840654322", "B-"),
            ("P007", "Rajan", "Pillai", "1958-09-25", "MALE", "9789012345", "9789012345", "rajan.pillai@example.com", "22, OMR Road", "Chennai", "Tamil Nadu", "600096", "Anitha Rajan", "9789012346", "A-"),
            ("P008", "Kavitha", "Sundaram", "1988-02-14", "FEMALE", "9789054321", "9789054321", "kavitha.s@example.com", "67, Mylapore", "Chennai", "Tamil Nadu", "600004", "Sundaram K", "9789054322", "O+"),
            ("P009", "Dinesh", "Chandra", "1995-01-20", "MALE", "9444012345", "9444012345", "dinesh.c@example.com", "89, Adyar", "Chennai", "Tamil Nadu", "600020", "Chandra Bose", "9444012346", "B+"),
            ("P010", "Usha", "Iyer", "1969-05-14", "FEMALE", "9444054321", "9444054321", "usha.iyer@example.com", "3, West Mambalam", "Chennai", "Tamil Nadu", "600033", "Subramanian Iyer", "9444054322", "AB-")
        ]
        
        patient_ids = {}
        for code, fname, lname, dob, gen, phone, wa, email, addr, city, state, pin, e_name, e_phone, blood in patients_data:
            cur.execute("""
                INSERT INTO patients (patient_code, first_name, last_name, date_of_birth, gender, phone, whatsapp_number, email, address, city, state, pincode, emergency_contact_name, emergency_contact_phone, blood_group, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'ACTIVE')
                ON CONFLICT (patient_code) DO UPDATE
                SET first_name = EXCLUDED.first_name, last_name = EXCLUDED.last_name, phone = EXCLUDED.phone
                RETURNING id;
            """, (code, fname, lname, dob, gen, phone, wa, email, addr, city, state, pin, e_name, e_phone, blood))
            patient_ids[code] = cur.fetchone()[0]
            
        # 7. Insert Appointments (At least 10 with different statuses)
        print("Seeding Appointments...")
        # Get doctor user ids for created_by_user_id, cancelled_by_user_id
        admin_uid = user_ids["admin"]
        doc1_uid = user_ids["doc1"]
        doc2_uid = user_ids["doc2"]
        
        # Appointment date is next week
        appt_date_1 = (datetime.date.today() + datetime.timedelta(days=3)).strftime("%Y-%m-%d")
        appt_date_2 = (datetime.date.today() + datetime.timedelta(days=4)).strftime("%Y-%m-%d")
        
        # Format: (booking_id, patient_code, doctor_code, dept_code, date, time, status, source, reason, cancel_reason, resched_reason, cancelled_by_uid, rescheduled_by_uid, created_by_uid)
        appointments_data = [
            ("BK001", "P001", "DR001", "D001", appt_date_1, "09:00:00", "BOOKED", "WHATSAPP_TEXT", "Fever and cough for 3 days", None, None, None, None, None),
            ("BK002", "P002", "DR001", "D001", appt_date_1, "09:30:00", "CONFIRMED", "ADMIN", "Regular diabetic check-up", None, None, None, None, admin_uid),
            ("BK003", "P003", "DR001", "D001", appt_date_1, "10:00:00", "COMPLETED", "DOCTOR", "Review of blood reports", None, None, None, None, doc1_uid),
            ("BK004", "P004", "DR001", "D001", appt_date_1, "10:30:00", "CANCELLED", "WHATSAPP_VOICE", "Severe joint pain", "Patient cannot travel due to heavy rain", None, admin_uid, None, None),
            ("BK005", "P005", "DR001", "D001", appt_date_1, "10:30:00", "BOOKED", "ADMIN", "Thyroid review", None, None, None, None, admin_uid), # Slot freed by BK004, so BK005 booked successfully!
            ("BK006", "P006", "DR002", "D002", appt_date_2, "14:00:00", "CONFIRMED", "WHATSAPP_TEXT", "Chest tightness during walk", None, None, None, None, None),
            ("BK007", "P007", "DR002", "D002", appt_date_2, "14:30:00", "RESCHEDULED", "ADMIN", "Hypertension follow-up", None, "Patient requested later slot", None, admin_uid, admin_uid),
            ("BK008", "P007", "DR002", "D002", appt_date_2, "15:30:00", "CONFIRMED", "ADMIN", "Hypertension follow-up - Rescheduled", None, None, None, None, admin_uid), # Rescheduled row for BK007
            ("BK009", "P008", "DR002", "D002", appt_date_2, "15:00:00", "BOOKED", "WHATSAPP_VOICE", "Heart palpitations", None, None, None, None, None),
            ("BK010", "P009", "DR001", "D001", appt_date_1, "11:00:00", "NO_SHOW", "ADMIN", "General fatigue", None, None, None, None, admin_uid),
            ("BK011", "P010", "DR002", "D002", appt_date_2, "16:00:00", "COMPLETED", "DOCTOR", "Annual cardiac assessment", None, None, None, None, doc2_uid)
        ]
        
        appt_ids = {}
        for b_id, p_code, d_code, dept_code, d_val, t_val, stat, src, reason, c_reason, r_reason, c_by, r_by, cr_by in appointments_data:
            cur.execute("""
                INSERT INTO appointments (booking_id, patient_id, doctor_id, department_id, appointment_date, appointment_time, status, booking_source, patient_reason, cancellation_reason, reschedule_reason, cancelled_by_user_id, rescheduled_by_user_id, created_by_user_id, cancelled_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (booking_id) DO UPDATE
                SET status = EXCLUDED.status, appointment_date = EXCLUDED.appointment_date, appointment_time = EXCLUDED.appointment_time
                RETURNING id;
            """, (b_id, patient_ids[p_code], doc_ids[d_code], dept_ids[dept_code], d_val, t_val, stat, src, reason, c_reason, r_reason, c_by, r_by, cr_by, datetime.datetime.now() if stat == 'CANCELLED' else None))
            appt_ids[b_id] = cur.fetchone()[0]
            
        # 8. Insert Pre-Admissions (At least 3 records)
        print("Seeding Pre-Admissions...")
        pre_admissions_data = [
            ("PA001", "P001", "BK001", (datetime.date.today() + datetime.timedelta(days=4)).strftime("%Y-%m-%d"), "INPATIENT", "DOCUMENTS_PENDING", "Aadhaar Card, Employer ID, Insurance Card", None, "Fast 8 hours before admission", "Patient needs to submit corporate policy card"),
            ("PA002", "P003", "BK003", (datetime.date.today() + datetime.timedelta(days=5)).strftime("%Y-%m-%d"), "SURGERY", "READY", None, "Aadhaar Card, Lab Reports, Pre-op Consent", "Report to Ward 3B at 6 AM", "All checks cleared by anesthesia team"),
            ("PA003", "P006", "BK006", (datetime.date.today() + datetime.timedelta(days=6)).strftime("%Y-%m-%d"), "DAYCARE", "PENDING", "Aadhaar Card", None, "No special prep required", "Awaiting physician clearance check")
        ]
        
        for pa_code, p_code, bk_id, adm_date, adm_type, stat, pending_docs, sub_docs, instr, rem in pre_admissions_data:
            cur.execute("""
                INSERT INTO pre_admissions (pre_admission_code, patient_id, appointment_id, expected_admission_date, admission_type, status, pending_documents, submitted_documents, instructions, remarks)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (pre_admission_code) DO UPDATE
                SET status = EXCLUDED.status, expected_admission_date = EXCLUDED.expected_admission_date;
            """, (pa_code, patient_ids[p_code], appt_ids[bk_id], adm_date, adm_type, stat, pending_docs, sub_docs, instr, rem))
            
        # 9. Insert Knowledge Documents
        print("Seeding Knowledge Documents...")
        knowledge_docs_data = [
            ("KD001", "Meridian Hospital FAQ", "HOSPITAL_PROFILE", "Meridian Hospital general info brochure", "Welcome to Meridian Hospital, Chennai. We are a leading 350-bed multi-specialty tertiary care hospital. Our OPD hours are Monday to Saturday, 8:00 AM to 8:00 PM. Emergencies are handled 24/7. Cashless billing is supported for major insurance providers.", "ENGLISH"),
            ("KD002", "Appointment Cancellation Policy", "CANCELLATION_POLICY", "Hospital policy manual v2", "Appointments booked through the Patient Desk or WhatsApp can be cancelled up to 2 hours prior to the scheduled slot. If cancelled on time, a full refund of the consulting fee is processed within 5-7 working days. No-shows are charged 50% of the consultation fee.", "ENGLISH"),
            ("KD003", "Pre-Admission Requirements", "PRE_ADMISSION", "Pre-admission desk guidelines", "For planned admissions (Inpatient/Surgery), patients must pre-register at least 24 hours prior. Mandatory documents include Aadhaar Card/Passport, Insurance Card, and Referral Note. Daycare procedures require check-in 1 hour prior to slot.", "ENGLISH")
        ]
        
        doc_db_ids = {}
        for code, title, doc_type, source, content, lang in knowledge_docs_data:
            cur.execute("""
                INSERT INTO knowledge_documents (document_code, title, document_type, source, content, language, version, status)
                VALUES (%s, %s, %s, %s, %s, %s, '1.0', 'ACTIVE')
                ON CONFLICT (document_code) DO UPDATE
                SET content = EXCLUDED.content, title = EXCLUDED.title
                RETURNING id;
            """, (code, title, doc_type, source, content, lang))
            doc_db_ids[code] = cur.fetchone()[0]
            
        # 10. Insert Knowledge Chunks (with 1536-dim mock vector embeddings)
        print("Seeding Knowledge Chunks...")
        # Document 1 (FAQ) Chunk
        cur.execute("""
            INSERT INTO knowledge_chunks (document_id, chunk_number, content, token_count, metadata, embedding)
            VALUES (%s, %s, %s, %s, %s, %s);
        """, (doc_db_ids["KD001"], 1, "OPD hours are Monday to Saturday, 8:00 AM to 8:00 PM. Emergencies are handled 24/7 at our main campus in Chennai.", 30, json.dumps({"section": "OPD Timings"}), get_mock_vector()))
        
        # Document 2 (Cancellation) Chunk
        cur.execute("""
            INSERT INTO knowledge_chunks (document_id, chunk_number, content, token_count, metadata, embedding)
            VALUES (%s, %s, %s, %s, %s, %s);
        """, (doc_db_ids["KD002"], 1, "Appointments can be cancelled up to 2 hours prior to the slot. No-shows incur 50% consultation charges.", 25, json.dumps({"section": "Cancellation"}), get_mock_vector()))
        
        # Document 3 (Pre-admission) Chunk
        cur.execute("""
            INSERT INTO knowledge_chunks (document_id, chunk_number, content, token_count, metadata, embedding)
            VALUES (%s, %s, %s, %s, %s, %s);
        """, (doc_db_ids["KD003"], 1, "For planned admissions, pre-register 24 hours prior. Required documents: Aadhaar, Insurance Card, Referral Note.", 25, json.dumps({"section": "Registration"}), get_mock_vector()))
        
        # 11. Insert Conversations
        print("Seeding Conversations...")
        cur.execute("""
            INSERT INTO conversations (conversation_code, patient_id, whatsapp_number, channel, language, current_intent, conversation_status)
            VALUES 
                ('CONV001', %s, '9876543210', 'WHATSAPP', 'ENGLISH', 'BOOK_APPOINTMENT', 'ACTIVE'),
                ('CONV002', %s, '8765432109', 'WHATSAPP', 'ENGLISH', 'CANCEL_APPOINTMENT', 'COMPLETED'),
                ('CONV003', %s, '7654321098', 'WHATSAPP', 'ENGLISH', 'PRE_ADMISSION', 'ESCALATED')
            RETURNING id, conversation_code;
        """, (patient_ids["P001"], patient_ids["P002"], patient_ids["P003"]))
        
        conv_ids = {code: c_id for c_id, code in cur.fetchall()}
        
        # 12. Insert Messages
        print("Seeding Messages...")
        messages_data = [
            (conv_ids["CONV001"], "PATIENT", "TEXT", "Hi, I need an appointment with Dr. Arun Kumar", "ENGLISH", "BOOK_APPOINTMENT", {}),
            (conv_ids["CONV001"], "AI_AGENT", "TEXT", "Hello! Dr. Arun Kumar is available on Monday at 09:00 AM, 09:30 AM, and 10:00 AM. Would you like to book one of these slots?", "ENGLISH", "BOOK_APPOINTMENT", {}),
            (conv_ids["CONV001"], "PATIENT", "TEXT", "Book 09:00 AM slot please", "ENGLISH", "BOOK_APPOINTMENT", {}),
            (conv_ids["CONV001"], "AI_AGENT", "TEXT", "Great! Your appointment is booked. Booking ID is BK001.", "ENGLISH", "BOOK_APPOINTMENT", {"booking_id": "BK001"}),
            
            (conv_ids["CONV002"], "PATIENT", "TEXT", "Please cancel my appointment BK004", "ENGLISH", "CANCEL_APPOINTMENT", {"booking_id": "BK004"}),
            (conv_ids["CONV002"], "AI_AGENT", "TEXT", "Your appointment BK004 has been successfully cancelled.", "ENGLISH", "CANCEL_APPOINTMENT", {})
        ]
        
        for c_id, sender, m_type, m_text, lang, intent, meta in messages_data:
            cur.execute("""
                INSERT INTO messages (conversation_id, sender_type, message_type, message_text, language, intent, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s);
            """, (c_id, sender, m_type, m_text, lang, intent, json.dumps(meta)))
            
        # 13. Insert Notifications
        print("Seeding Notifications...")
        notifications_data = [
            (patient_ids["P001"], appt_ids["BK001"], "APPOINTMENT_CONFIRMED", "WHATSAPP", "Dear Ramesh Kumar, your appointment with Dr. Arun Kumar is confirmed for 2026-09-01 at 09:00 AM.", None, "DELIVERED"),
            (patient_ids["P004"], appt_ids["BK004"], "APPOINTMENT_CANCELLED", "WHATSAPP", "Dear Anitha Nair, your appointment with Dr. Arun Kumar on 2026-09-01 at 10:30 AM has been cancelled.", "Patient cannot travel due to heavy rain", "SENT"),
            (patient_ids["P002"], appt_ids["BK002"], "APPOINTMENT_REMINDER", "EMAIL", "Dear Anitha Nair, this is a reminder for your appointment with Dr. Arun Kumar tomorrow at 09:30 AM.", None, "DELIVERED")
        ]
        
        for p_id, a_id, n_type, chan, msg, reason, stat in notifications_data:
            cur.execute("""
                INSERT INTO notifications (patient_id, appointment_id, notification_type, channel, message, reason, status, sent_at, delivered_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP - INTERVAL '1 day', CURRENT_TIMESTAMP - INTERVAL '1 day');
            """, (p_id, a_id, n_type, chan, msg, reason, stat))
            
        # 14. Insert Audit Logs
        print("Seeding Audit Logs...")
        cur.execute("""
            INSERT INTO audit_logs (user_id, action, entity_type, entity_id, old_values, new_values, reason)
            VALUES 
                (%s, 'CREATE_PATIENT', 'patients', %s, NULL, '{"patient_code": "P001", "name": "Ramesh Kumar"}', 'WhatsApp Desk Self-registration'),
                (%s, 'CREATE_APPOINTMENT', 'appointments', %s, NULL, '{"booking_id": "BK001", "time": "09:00"}', 'WhatsApp appointment booking'),
                (%s, 'CANCEL_APPOINTMENT', 'appointments', %s, '{"status": "CONFIRMED"}', '{"status": "CANCELLED"}', 'Cancelled by user due to rain');
        """, (user_ids["admin"], patient_ids["P001"], user_ids["admin"], appt_ids["BK001"], user_ids["admin"], appt_ids["BK004"]))
        
        # 15. Insert Agent Action Logs
        print("Seeding Agent Action Logs...")
        agent_logs_data = [
            (conv_ids["CONV001"], patient_ids["P001"], "GET_DOCTOR_AVAILABILITY", "BOOK_APPOINTMENT", {"doctor_id": 1}, {"available_slots": ["09:00", "09:30", "10:00"]}, "SUCCESS"),
            (conv_ids["CONV001"], patient_ids["P001"], "BOOK_APPOINTMENT", "BOOK_APPOINTMENT", {"doctor_id": 1, "time": "09:00", "date": appt_date_1}, {"booking_id": "BK001", "status": "BOOKED"}, "SUCCESS"),
            (conv_ids["CONV002"], patient_ids["P002"], "CANCEL_APPOINTMENT", "CANCEL_APPOINTMENT", {"booking_id": "BK004"}, {"status": "CANCELLED"}, "SUCCESS")
        ]
        
        for c_id, p_id, act_name, intent, inp, out, stat in agent_logs_data:
            cur.execute("""
                INSERT INTO agent_action_logs (conversation_id, patient_id, action_name, intent, input_data, output_data, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s);
            """, (c_id, p_id, act_name, intent, json.dumps(inp), json.dumps(out), stat))
            
        # Commit transaction
        conn.commit()
        print("Database seeded successfully with all sample data!")
        
    except Exception as e:
        print(f"Seeding failed: rollback initiated. Error: {e}")
        conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    seed_data()
