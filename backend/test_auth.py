import sys
import os
import unittest
import time
from fastapi.testclient import TestClient

# Force UTF-8 output on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
if sys.stderr.encoding != 'utf-8':
    sys.stderr = open(sys.stderr.fileno(), mode='w', encoding='utf-8', buffering=1)

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import app
from api.auth_helper import encode_token, decode_token, get_hashed_password, verify_password

client = TestClient(app)
RESULTS = []

def test(name):
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
        return wrapper
    return decorator
test.__test__ = False

# ─── Password Verification Tests ──────────────────────────────────────────────

@test("Password verification and hashing work with bcrypt")
def test_password_cryptography():
    pwd = "mysecretpassword123"
    hashed = get_hashed_password(pwd)
    assert hashed != pwd, "Hashed password should not equal plain password"
    assert verify_password(pwd, hashed) is True, "Valid password verification should succeed"
    assert verify_password("wrongpassword", hashed) is False, "Invalid password verification should fail"

# ─── JWT Signature and Expiration Tests ────────────────────────────────────────

@test("JWT token encoding and decoding works")
def test_jwt_operations():
    payload = {"user_id": 1, "username": "admin", "role": "ADMIN"}
    token = encode_token(payload)
    decoded = decode_token(token)
    assert decoded is not None, "Token decoding should succeed"
    assert decoded["username"] == "admin", f"Expected username admin, got {decoded.get('username')}"
    assert decoded["role"] == "ADMIN", "Role should match payload"

@test("Expired JWT tokens are rejected")
def test_jwt_expiration():
    payload = {"user_id": 1, "username": "admin", "role": "ADMIN", "exp": int(time.time()) - 10}
    token = encode_token(payload)
    decoded = decode_token(token)
    assert decoded is None, "Expired token decoding should fail (return None)"

# ─── API Login/Logout Endpoint Tests ──────────────────────────────────────────

@test("Admin login succeeds with valid credentials")
def test_admin_login():
    response = client.post("/api/auth/login", json={"username": "admin", "password": "admin", "role": "admin"})
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert data["success"] is True, "Login response success should be True"
    assert "token" in data, "Token should be returned in login response"
    assert data["user"]["role"] == "admin", "Role should be admin"

@test("Doctor login succeeds with valid credentials")
def test_doctor_login():
    response = client.post("/api/auth/login", json={"username": "doc1", "password": "doc1", "role": "doctor"})
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert data["success"] is True
    assert data["user"]["role"] == "doctor"
    assert data["user"]["doctorId"] is not None, "doctorId should be resolved and returned for doctors"
    assert data["user"]["department"] == "General Medicine", f"Expected General Medicine, got {data['user']['department']}"

@test("Login fails with incorrect password")
def test_login_incorrect_password():
    response = client.post("/api/auth/login", json={"username": "admin", "password": "wrong_password", "role": "admin"})
    assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    assert "Invalid password" in response.json()["detail"], "Should return clear invalid password error message"

@test("Login fails with incorrect role request")
def test_login_incorrect_role():
    # Attempting to log in as doctor account with admin role
    response = client.post("/api/auth/login", json={"username": "doc1", "password": "doc1", "role": "admin"})
    assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    assert "does not have admin access" in response.json()["detail"], "Should reject incorrect role assignment"

# ─── Endpoint Role-Based Access Control (RBAC) Tests ─────────────────────────

@test("Unauthenticated requests to protected endpoints return 401")
def test_unauthenticated_access():
    response = client.get("/api/dashboard/summary")
    assert response.status_code == 401, f"Expected 401, got {response.status_code}"

@test("Admin has full access to admin-only dashboard endpoints")
def test_admin_access():
    # Admin login to retrieve token
    login_resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin", "role": "admin"})
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Access Doctors list
    resp = client.get("/api/dashboard/doctors", headers=headers)
    assert resp.status_code == 200, f"Admin doctors access failed: {resp.status_code}"
    
    # 2. Access Departments list
    resp = client.get("/api/dashboard/departments", headers=headers)
    assert resp.status_code == 200, f"Admin departments access failed: {resp.status_code}"

@test("Doctor is blocked from admin-only endpoints (returns 403)")
def test_doctor_rbac_blocks():
    # Doctor login to retrieve token
    login_resp = client.post("/api/auth/login", json={"username": "doc1", "password": "doc1", "role": "doctor"})
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Restrict doctor from listing other doctors
    resp = client.get("/api/dashboard/doctors", headers=headers)
    assert resp.status_code == 403, f"Doctor doctor-list bypass succeeded (got {resp.status_code}, expected 403)"
    
    # 2. Restrict doctor from listing departments
    resp = client.get("/api/dashboard/departments", headers=headers)
    assert resp.status_code == 403, f"Doctor department-list bypass succeeded (got {resp.status_code}, expected 403)"

# ─── Doctor Scope Constraints & Scoping Verification Tests ─────────────────────

@test("Doctor summary KPI matches doctor-specific appointments only")
def test_doctor_scope_kpis():
    # doc1 login (Arun Kumar)
    login_resp = client.post("/api/auth/login", json={"username": "doc1", "password": "doc1", "role": "doctor"})
    doc1_data = login_resp.json()
    doc1_token = doc1_data["token"]
    doc1_id = doc1_data["user"]["doctorId"]
    
    headers = {"Authorization": f"Bearer {doc1_token}"}
    resp = client.get("/api/dashboard/summary", headers=headers)
    assert resp.status_code == 200
    summary = resp.json()
    
    # Verify that the doctor only counts active doctors as 1
    assert summary["doctors"]["active"] == 1, "Doctor should see active doctors count as 1"

@test("Doctor cannot view detail of patient not assigned to them")
def test_doctor_patient_isolation():
    # doc2 login (Priya Ramesh, Cardology)
    login_resp = client.post("/api/auth/login", json={"username": "doc2", "password": "doc2", "role": "doctor"})
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Try to view a patient who doesn't have appointments with doc2 (Dr. Priya Ramesh)
    # Let's search for patient detail for patient id 1 (Ramesh Kumar - who has appointment with Dr. Arun Kumar, General Medicine)
    resp = client.get("/api/dashboard/patients/1", headers=headers)
    # Dr. Priya Ramesh has no appointment with Ramesh Kumar, so this should return 403 Forbidden!
    assert resp.status_code == 403, f"Expected 403 Forbidden for unauthorized patient view, got {resp.status_code}"

@test("Doctor cannot update status of appointment not assigned to them")
def test_doctor_appointment_isolation():
    # doc2 login (Priya Ramesh)
    login_resp2 = client.post("/api/auth/login", json={"username": "doc2", "password": "doc2", "role": "doctor"})
    token2 = login_resp2.json()["token"]
    headers2 = {"Authorization": f"Bearer {token2}"}
    
    # Let's try to cancel or complete an appointment of Dr. Arun Kumar (e.g., booking_id "BK001")
    # BK001 is assigned to doc1 (Dr. Arun Kumar)
    resp = client.patch("/api/dashboard/appointments/BK001/status", json={"status": "COMPLETED"}, headers=headers2)
    assert resp.status_code == 403, f"Expected 403 Forbidden for unauthorized appointment edit, got {resp.status_code}"

# ─── Main Runner ─────────────────────────────────────────────────────────────

def run_all_tests():
    print("\n=================================================================")
    print("  Admin/Doctor Authentication & RBAC — Test Suite")
    print("=================================================================\n")
    
    tests = [
        test_password_cryptography,
        test_jwt_operations,
        test_jwt_expiration,
        test_admin_login,
        test_doctor_login,
        test_login_incorrect_password,
        test_login_incorrect_role,
        test_unauthenticated_access,
        test_admin_access,
        test_doctor_rbac_blocks,
        test_doctor_scope_kpis,
        test_doctor_patient_isolation,
        test_doctor_appointment_isolation
    ]
    
    for t in tests:
        t()
        
    print("\n=================================================================")
    passed = len([r for r in RESULTS if r[0] == "PASS"])
    failed = len([r for r in RESULTS if r[0] == "FAIL"])
    errors = len([r for r in RESULTS if r[0] == "ERROR"])
    print(f"  TOTAL: {len(RESULTS)}  |  PASS: {passed}  |  FAIL: {failed}  |  ERROR: {errors}")
    print("=================================================================\n")
    
    if failed > 0 or errors > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    run_all_tests()
