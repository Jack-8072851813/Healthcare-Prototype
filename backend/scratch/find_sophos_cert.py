import ssl
import sys

def list_system_certs():
    print("Checking Windows SYSTEM ROOT store cert subjects...")
    certs = ssl.enum_certificates("ROOT")
    count = 0
    for cert_der, encoding, trust_flags in certs:
        count += 1
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
        try:
            cert = x509.load_der_x509_certificate(cert_der, default_backend())
            print(f"{count}: Subject: {cert.subject}")
            print(f"   Issuer: {cert.issuer}")
        except Exception as e:
            print(f"{count}: Error parsing: {e}")

if __name__ == "__main__":
    list_system_certs()
