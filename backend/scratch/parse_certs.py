import os
import sys

def parse_dump():
    dump_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "certs_dump.txt")
    if not os.path.exists(dump_path):
        print("Dump file not found!")
        return

    # Try reading as UTF-16LE (default Out-File encoding)
    try:
        with open(dump_path, "r", encoding="utf-16le") as f:
            content = f.read()
    except Exception as e:
        print(f"Failed to read as UTF-16LE: {e}")
        try:
            with open(dump_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e2:
            print(f"Failed to read as UTF-8: {e2}")
            return

    # Find certificate blocks
    import re
    certs = re.findall(r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", content, re.DOTALL)
    print(f"Found {len(certs)} certificate blocks in the dump.")
    
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend

    for i, cert_str in enumerate(certs):
        print(f"\n--- Certificate {i} ---")
        try:
            cert_bytes = cert_str.encode("utf-8")
            cert = x509.load_pem_x509_certificate(cert_bytes, default_backend())
            print("Subject:", cert.subject)
            print("Issuer:", cert.issuer)
            print("Serial:", cert.serial_number)
            
            # Save certificate to file
            cert_filename = f"extracted_cert_{i}.pem"
            target_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), cert_filename)
            with open(target_path, "w", encoding="utf-8") as out_f:
                out_f.write(cert_str)
            print(f"Saved to {target_path}")
        except Exception as e:
            print(f"Error parsing certificate {i}: {e}")

if __name__ == "__main__":
    parse_dump()
