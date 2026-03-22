import argparse
import sys
import requests
import urllib3

# Suppress insecure request warnings if testing with local self-signed CAs without trusting them at the OS level
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from mock_watt.security.signature import SecurityEngine
from mock_watt.transport.soap_builder import SoapBuilder

def execute_request(payload_path: str, target_url: str, cert_path: str, key_path: str, ca_path: str = None):
    """
    Executes an outbound IEC 62325-504 request to a target B2B endpoint.
    """
    print(f"⚡ Mock-Watt Outbound Executor")
    print(f"--------------------------------------------------")
    print(f"📄 Payload: {payload_path}")
    print(f"🎯 Target:  {target_url}")
    
    try:
        # 1. Load the raw business payload
        with open(payload_path, "rb") as file:
            raw_xml = file.read()
            
        # 2. Cryptographically sign the payload
        print("🔒 Signing payload (Exclusive C14N + XML-DSig)...")
        security = SecurityEngine(key_path=key_path, cert_path=cert_path)
        signed_xml = security.sign_payload(raw_xml)
        
        # 3. Wrap in IEC 62325-504 SOAP Envelope
        print("✉️  Wrapping in SOAP PutMessage envelope...")
        soap_envelope = SoapBuilder.wrap_put_message(signed_xml)
        
        # 4. Execute the mTLS HTTP Request
        print("🌐 Transmitting via mTLS...")
        headers = {
            "Content-Type": "application/soap+xml; charset=utf-8",
            "SOAPAction": "urn:iec62325.504:v1.0#PutMessage" 
        }
        
        response = requests.post(
            url=target_url,
            data=soap_envelope,
            headers=headers,
            cert=(cert_path, key_path), # Injects the client certificate for mTLS
            verify=ca_path if ca_path else False, # Verifies the target's Root CA
            timeout=10
        )
        
        # 5. Output Results
        print(f"--------------------------------------------------")
        print(f"✅ Request Complete. Status Code: [{response.status_code}]")
        print(f"📥 Server Response:\n{response.text}")

    except Exception as e:
        print(f"\n❌ Execution Failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mock-Watt: Send IEC 62325-504 Message")
    parser.add_argument("--payload", required=True, help="Path to the raw XML business document")
    parser.add_argument("--url", required=True, help="Target HTTPS endpoint URL")
    parser.add_argument("--cert", required=True, help="Path to the Mock-Watt client certificate (.pem)")
    parser.add_argument("--key", required=True, help="Path to the Mock-Watt private key (.key)")
    parser.add_argument("--ca", required=False, help="Path to the Root CA to verify the server (optional for local dev)")
    
    args = parser.parse_args()
    
    execute_request(
        payload_path=args.payload,
        target_url=args.url,
        cert_path=args.cert,
        key_path=args.key,
        ca_path=args.ca
    )