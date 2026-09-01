import socket
import ssl
import sys
from cryptography import x509
from cryptography.hazmat.backends import default_backend

def get_certificate_chain(hostname, port=443):
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    
    print(f"Connecting to {hostname}:{port} to fetch binary cert...")
    with socket.create_connection((hostname, port)) as sock:
        with context.wrap_socket(sock, server_hostname=hostname) as ssock:
            der_cert = ssock.getpeercert(binary_form=True)
            cert = x509.load_der_x509_certificate(der_cert, default_backend())
            print("\nCertificate Subject:", cert.subject)
            print("Certificate Issuer:", cert.issuer)
            print("Valid From:", cert.not_valid_before_utc)
            print("Valid To:", cert.not_valid_after_utc)
            
            # Let's inspect the extensions
            print("\nExtensions:")
            for ext in cert.extensions:
                print(f"  {ext.oid._name}: {ext.value}")

if __name__ == "__main__":
    get_certificate_chain("graph.facebook.com")
