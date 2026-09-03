import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import db_config

# Ensure dotenv is loaded
db_config.load_dotenv()

def log_email_status(
    email_type: str,
    recipient: str,
    subject: str,
    status: str,
    appointment_id: int = None,
    doctor_id: int = None,
    provider_message_id: str = None,
    failure_reason: str = None
):
    """Inserts record into email_logs table."""
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        sent_at_sql = "now()" if "SENT" in status else "NULL"
        cur.execute(f"""
            INSERT INTO email_logs 
            (email_type, recipient, appointment_id, doctor_id, subject, status, provider_message_id, failure_reason, sent_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, {sent_at_sql});
        """, (email_type, recipient, appointment_id, doctor_id, subject, status, provider_message_id, failure_reason))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print("Failed to log email status to DB:", e)
    finally:
        cur.close()
        conn.close()

def _send_email_raw(to_email: str, subject: str, body_html: str, body_text: str) -> bool:
    """Internal helper to dispatch email via standard SMTP."""
    db_config.load_dotenv()
    
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    smtp_from_email = os.getenv("SMTP_FROM_EMAIL", smtp_user or "no-reply@meridianhospital.com").strip()
    smtp_from_name = os.getenv("SMTP_FROM_NAME", "Meridian Hospital").strip()

    print(f"\n[EMAIL DISPATCH] To: {to_email} | Subject: {subject} | SMTP User: {smtp_user}")
    
    # If credentials are not provided, simulate sending in logs
    if not smtp_user or not smtp_password:
        print("[EMAIL DISPATCH] Notice: SMTP credentials not set in .env. Email simulated successfully.")
        print(f"=== EMAIL CONTENT ===\n{body_text}\n=====================\n")
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{smtp_from_name} <{smtp_from_email}>"
        msg["To"] = to_email

        msg.attach(MIMEText(body_text, "plain"))
        msg.attach(MIMEText(body_html, "html"))

        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_from_email, [to_email], msg.as_string())
            
        print(f"[EMAIL DISPATCH SUCCESS] Real email delivered to {to_email}")
        return True
    except Exception as e:
        print(f"[EMAIL DISPATCH ERROR] Failed to send email to {to_email}: {e}")
        print(f"=== SIMULATED EMAIL BODY ===\n{body_text}\n===========================\n")
        return False

def send_welcome_email(doctor_email: str, doctor_name: str, username: str, password: str, doctor_id: int = None) -> bool:
    """Send welcome email with login credentials to a newly registered doctor."""
    if not doctor_email:
        print("[EMAIL DISPATCH] Doctor email missing. Skipping welcome email.")
        return False

    subject = "Welcome to Meridian Hospital - Doctor Account Created"
    
    body_text = f"""Dear {doctor_name},

Welcome to Meridian Hospital! Your doctor portal account has been successfully created.

Here are your login credentials:
Portal Link: http://localhost:5173/login
Username: {username}
Temporary Password: {password}

Please log in and update your password under your Profile settings.

Warm regards,
Meridian Hospital Management Team
Kolathur, Chennai
"""

    body_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #E2E8F0; border-radius: 8px; padding: 24px; color: #2D3748;">
        <div style="text-align: center; border-bottom: 2px solid #2B6CB0; padding-bottom: 16px; margin-bottom: 20px;">
            <h2 style="color: #2B6CB0; margin: 0;">Meridian Hospital</h2>
            <p style="color: #718096; margin: 4px 0 0 0; font-size: 14px;">The Family Hospital · Kolathur, Chennai</p>
        </div>
        
        <h3 style="color: #2D3748;">Welcome to the Medical Team, {doctor_name}!</h3>
        <p>Your doctor portal account has been successfully registered by the Administrator.</p>
        
        <div style="background-color: #EDF2F7; padding: 16px; border-radius: 6px; margin: 20px 0;">
            <h4 style="margin: 0 0 10px 0; color: #2B6CB0;">Your Login Credentials</h4>
            <p style="margin: 6px 0;"><strong>Username:</strong> <code style="background: #E2E8F0; padding: 2px 6px; border-radius: 4px;">{username}</code></p>
            <p style="margin: 6px 0;"><strong>Password:</strong> <code style="background: #E2E8F0; padding: 2px 6px; border-radius: 4px;">{password}</code></p>
        </div>
        
        <p>You can access the Doctor Portal here: <a href="http://localhost:5173/login" style="color: #2B6CB0; font-weight: bold;">Login to Doctor Portal</a></p>
        <p style="font-size: 13px; color: #718096; margin-top: 24px;">For security, please change your password after your first login in your Profile section.</p>
        
        <hr style="border: none; border-top: 1px solid #E2E8F0; margin: 24px 0;" />
        <p style="font-size: 12px; color: #A0AEC0; text-align: center;">This is an automated notification from Meridian Hospital Management System.</p>
    </div>
    """

    success = _send_email_raw(doctor_email, subject, body_html, body_text)
    status_code = "DOCTOR_WELCOME_EMAIL_SENT" if success else "DOCTOR_WELCOME_EMAIL_FAILED"
    fail_msg = None if success else "SMTP delivery failed"
    log_email_status("DOCTOR_WELCOME", doctor_email, subject, status_code, doctor_id=doctor_id, failure_reason=fail_msg)
    return success

def send_patient_appointment_confirmation_email(
    patient_email: str,
    patient_name: str,
    appointment_for: str,
    doctor_name: str,
    department_name: str,
    appointment_date: str,
    appointment_time: str,
    booking_id: str,
    appointment_id: int = None
) -> bool:
    """Send appointment confirmation email to patient or parent/guardian."""
    if not patient_email:
        print("[EMAIL DISPATCH] Patient email missing. Skipping appointment confirmation email.")
        return False

    subject = "Appointment Confirmation - Meridian Hospital"
    patient_type_label = f" (for {appointment_for})" if appointment_for and appointment_for.upper() != "SELF" else ""

    body_text = f"""Dear {patient_name},

Thank you for choosing Meridian Hospital! Your appointment has been successfully confirmed.

Appointment Details:
--------------------
Booking ID: {booking_id}
Patient Name: {patient_name}{patient_type_label}
Doctor: {doctor_name}
Department: {department_name}
Date: {appointment_date}
Time: {appointment_time}

Hospital Location:
Meridian Hospital, Kolathur, Chennai - 600099
Phone: +91 44 2654 3210

Please arrive 15 minutes before your scheduled appointment time.

Warm regards,
Meridian Hospital Scheduling Team
"""

    body_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #E2E8F0; border-radius: 8px; padding: 24px; color: #2D3748;">
        <div style="background-color: #2B6CB0; padding: 16px; border-radius: 6px 6px 0 0; color: white; text-align: center;">
            <h3 style="margin: 0;">Appointment Confirmed</h3>
            <p style="margin: 4px 0 0 0; font-size: 14px;">Meridian Hospital · Kolathur, Chennai</p>
        </div>
        <div style="padding: 20px 0;">
            <p>Dear <strong>{patient_name}</strong>,</p>
            <p>Your appointment at Meridian Hospital has been confirmed successfully!</p>
            
            <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
                <tr style="background-color: #F7FAFC;">
                    <td style="padding: 8px 12px; font-weight: bold; border: 1px solid #E2E8F0;">Booking ID</td>
                    <td style="padding: 8px 12px; border: 1px solid #E2E8F0; color: #2B6CB0; font-weight: bold;">{booking_id}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 12px; font-weight: bold; border: 1px solid #E2E8F0;">Patient Name</td>
                    <td style="padding: 8px 12px; border: 1px solid #E2E8F0;">{patient_name}{patient_type_label}</td>
                </tr>
                <tr style="background-color: #F7FAFC;">
                    <td style="padding: 8px 12px; font-weight: bold; border: 1px solid #E2E8F0;">Doctor</td>
                    <td style="padding: 8px 12px; border: 1px solid #E2E8F0;">{doctor_name}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 12px; font-weight: bold; border: 1px solid #E2E8F0;">Department</td>
                    <td style="padding: 8px 12px; border: 1px solid #E2E8F0;">{department_name}</td>
                </tr>
                <tr style="background-color: #F7FAFC;">
                    <td style="padding: 8px 12px; font-weight: bold; border: 1px solid #E2E8F0;">Date</td>
                    <td style="padding: 8px 12px; border: 1px solid #E2E8F0;">{appointment_date}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 12px; font-weight: bold; border: 1px solid #E2E8F0;">Time</td>
                    <td style="padding: 8px 12px; border: 1px solid #E2E8F0;">{appointment_time}</td>
                </tr>
            </table>
            
            <p style="font-size: 13px; color: #718096;">Please arrive 15 minutes prior to your appointment time.</p>
        </div>
        <div style="font-size: 12px; color: #A0AEC0; text-align: center; border-top: 1px solid #E2E8F0; padding-top: 12px;">
            Meridian Hospital · Kolathur, Chennai · Phone: +91 44 2654 3210
        </div>
    </div>
    """

    success = _send_email_raw(patient_email, subject, body_html, body_text)
    status_code = "EMAIL_SENT" if success else "EMAIL_FAILED"
    fail_msg = None if success else "SMTP delivery failed or credentials not configured"
    log_email_status("APPOINTMENT_CONFIRMATION", patient_email, subject, status_code, appointment_id=appointment_id, failure_reason=fail_msg)
    return success

def send_appointment_notification_email(
    doctor_email: str,
    doctor_name: str,
    patient_name: str,
    patient_phone: str,
    appointment_date: str,
    appointment_time: str,
    department_name: str,
    booking_id: str
) -> bool:
    """Send appointment alert email to doctor when a patient books an appointment."""
    if not doctor_email:
        print("[EMAIL DISPATCH] Doctor email missing. Skipping appointment notification email.")
        return False

    subject = f"New Appointment Booking [{booking_id}] — Patient: {patient_name}"
    
    body_text = f"""Dear {doctor_name},

A new appointment has been scheduled with you.

Appointment Details:
--------------------
Booking ID: {booking_id}
Patient Name: {patient_name}
Contact Number: {patient_phone or 'N/A'}
Date: {appointment_date}
Time: {appointment_time}
Department: {department_name}

Please check your Doctor Dashboard for more details.

Warm regards,
Meridian Hospital Scheduling System
"""

    body_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #E2E8F0; border-radius: 8px; padding: 24px; color: #2D3748;">
        <div style="background-color: #2B6CB0; padding: 16px; border-radius: 6px 6px 0 0; color: white; text-align: center;">
            <h3 style="margin: 0;">New Patient Appointment Notification</h3>
        </div>
        <div style="padding: 20px 0;">
            <p>Dear <strong>{doctor_name}</strong>,</p>
            <p>A new appointment has been booked for you at Meridian Hospital.</p>
            
            <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
                <tr style="background-color: #F7FAFC;">
                    <td style="padding: 8px 12px; font-weight: bold; border: 1px solid #E2E8F0;">Booking ID</td>
                    <td style="padding: 8px 12px; border: 1px solid #E2E8F0; color: #2B6CB0; font-weight: bold;">{booking_id}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 12px; font-weight: bold; border: 1px solid #E2E8F0;">Patient Name</td>
                    <td style="padding: 8px 12px; border: 1px solid #E2E8F0;">{patient_name}</td>
                </tr>
                <tr style="background-color: #F7FAFC;">
                    <td style="padding: 8px 12px; font-weight: bold; border: 1px solid #E2E8F0;">Patient Phone</td>
                    <td style="padding: 8px 12px; border: 1px solid #E2E8F0;">{patient_phone or '—'}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 12px; font-weight: bold; border: 1px solid #E2E8F0;">Appointment Date</td>
                    <td style="padding: 8px 12px; border: 1px solid #E2E8F0;">{appointment_date}</td>
                </tr>
                <tr style="background-color: #F7FAFC;">
                    <td style="padding: 8px 12px; font-weight: bold; border: 1px solid #E2E8F0;">Appointment Time</td>
                    <td style="padding: 8px 12px; border: 1px solid #E2E8F0;">{appointment_time}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 12px; font-weight: bold; border: 1px solid #E2E8F0;">Department</td>
                    <td style="padding: 8px 12px; border: 1px solid #E2E8F0;">{department_name}</td>
                </tr>
            </table>
            
            <p>You can manage your appointments on your <a href="http://localhost:5173/doctor/appointments" style="color: #2B6CB0; font-weight: bold;">Doctor Portal</a>.</p>
        </div>
        <div style="font-size: 12px; color: #A0AEC0; text-align: center; border-top: 1px solid #E2E8F0; padding-top: 12px;">
            Meridian Hospital · Kolathur, Chennai
        </div>
    </div>
    """

    return _send_email_raw(doctor_email, subject, body_html, body_text)

def send_otp_email(doctor_email: str, doctor_name: str, otp_code: str) -> bool:
    """Send OTP for Password Reset to Doctor's email."""
    if not doctor_email:
        print("[EMAIL DISPATCH] Doctor email missing. Skipping OTP email.")
        return False

    subject = "Password Reset OTP — Meridian Hospital Doctor Portal"
    
    body_text = f"""Dear {doctor_name},

Your OTP code to reset your password is: {otp_code}

This code is valid for 10 minutes. Do not share this OTP with anyone.

Regards,
Meridian Hospital Security Team
"""

    body_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; border: 1px solid #E2E8F0; border-radius: 8px; padding: 24px; color: #2D3748;">
        <h3 style="color: #2B6CB0; margin-top: 0;">Password Reset Request</h3>
        <p>Dear <strong>{doctor_name}</strong>,</p>
        <p>We received a request to reset your password for the Doctor Portal.</p>
        <div style="text-align: center; margin: 24px 0;">
            <span style="font-size: 32px; font-weight: bold; letter-spacing: 6px; background: #EDF2F7; padding: 12px 24px; border-radius: 8px; color: #2B6CB0;">{otp_code}</span>
        </div>
        <p style="font-size: 13px; color: #718096;">This OTP is valid for <strong>10 minutes</strong>. If you did not request a password reset, please ignore this email.</p>
    </div>
    """

    return _send_email_raw(doctor_email, subject, body_html, body_text)
