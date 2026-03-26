import argparse
import logging
import os
import ssl
import sys
from datetime import datetime

import requests
import urllib3
import uvicorn
from lxml import etree

# Suppress insecure request warnings for local testing
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from security.signature import SecurityEngine
from transport.soap_builder import SoapBuilder


def _detect_noun(raw_xml: bytes) -> str:
    """Extracts the local name of the root element to use as the IEC TC57 Noun."""
    root = etree.fromstring(raw_xml)
    # Strip namespace: "{http://...}MensagemOferBandaFRR" → "MensagemOferBandaFRR"
    return etree.QName(root).localname


def execute_request(
    payload_path: str,
    target_url: str,
    cert_path: str,
    key_path: str,
    ca_path: str | None = None,
    verb: str = "created",
    noun: str | None = None,
    store_request: bool = False,
    store_response: bool = False,
):
    """Executes the outbound IEC TC57 RequestMessage and optionally stores the request/response payloads."""
    print(f"⚡ Mock-Watt Outbound Executor")
    print(f"--------------------------------------------------")
    print(f"📄 Source Payload: {payload_path}")
    print(f"🎯 Target URL:     {target_url}")

    try:
        # 1. Load the raw business payload
        with open(payload_path, "rb") as file:
            raw_xml = file.read()

        # 2. Resolve the noun from the payload root element if not explicitly provided
        resolved_noun = noun if noun else _detect_noun(raw_xml)
        print(f"📋 Verb: {verb} / Noun: {resolved_noun}")

        # 3. Build unsigned RequestMessage, sign it, wrap in SOAP envelope
        print("✉️  Building SOAP 1.2 RequestMessage envelope...")
        security = SecurityEngine(key_path=key_path, cert_path=cert_path)
        req_msg = SoapBuilder.build_request_message(verb, resolved_noun, raw_xml)

        print("🔒 Signing RequestMessage (Inclusive C14N + XML-DSig)...")
        security.sign_request_message(req_msg)

        soap_envelope = SoapBuilder.wrap_in_envelope(req_msg)

        # 5. Optionally save the outgoing request envelope to data/outbound/
        if store_request:
            base_name = os.path.splitext(os.path.basename(payload_path))[0]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            outbound_dir = os.path.join(os.getcwd(), "data", "outbound")
            os.makedirs(outbound_dir, exist_ok=True)
            outbound_path = os.path.join(outbound_dir, f"{base_name}_{timestamp}.xml")
            with open(outbound_path, "wb") as out_file:
                out_file.write(soap_envelope)
            print(f"💾 Saved outbound envelope to: {outbound_path}")

        # 6. Transmit via mTLS
        print("🌐 Transmitting via mTLS...")
        headers = {
            "Content-Type": f'application/soap+xml; charset=utf-8; action="{verb}"',
        }

        response = requests.post(
            url=target_url,
            data=soap_envelope,
            headers=headers,
            cert=(cert_path, key_path),
            verify=ca_path if ca_path else False,
            timeout=10
        )

        # 7. Output Results
        print(f"--------------------------------------------------")
        print(f"✅ Request Complete. Status Code: [{response.status_code}]")
        print(f"📥 Server Response:\n{response.text}...")

        # 8. Optionally save the server response to data/inbound/
        if store_response:
            base_name = os.path.splitext(os.path.basename(payload_path))[0]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            inbound_dir = os.path.join(os.getcwd(), "data", "inbound")
            os.makedirs(inbound_dir, exist_ok=True)
            inbound_path = os.path.join(inbound_dir, f"{base_name}_{timestamp}_response.xml")
            with open(inbound_path, "wb") as in_file:
                in_file.write(response.content)
            print(f"💾 Saved server response to: {inbound_path}")

    except Exception as e:
        print(f"\n❌ Execution Failed: {str(e)}")
        sys.exit(1)


def execute_serve(
    cert_path: str,
    key_path: str,
    ca_path: str | None = None,
    host: str = "0.0.0.0",
    port: int = 8443,
):
    """Starts the Mock-Watt IEC 62325-504 gateway server with mTLS."""
    from server.app import app, configure

    print(f"⚡ Mock-Watt Gateway Server")
    print(f"--------------------------------------------------")
    print(f"🔒 Server cert:  {cert_path}")
    print(f"🔑 Server key:   {key_path}")
    print(f"🏛️  Root CA:      {ca_path or 'not set (mTLS disabled)'}")
    print(f"🌐 Listening on: https://{host}:{port}/ws504")
    print(f"--------------------------------------------------")

    configure(ca_cert_path=ca_path)

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(levelname)s [%(name)s] %(message)s",
    )

    ssl_cert_reqs = ssl.CERT_REQUIRED if ca_path else ssl.CERT_NONE

    uvicorn.run(
        app,
        host=host,
        port=port,
        ssl_certfile=cert_path,
        ssl_keyfile=key_path,
        ssl_ca_certs=ca_path,
        ssl_cert_reqs=ssl_cert_reqs,
    )


def main():
    """Entry point for the 'mock-watt' CLI command."""
    parser = argparse.ArgumentParser(description="Mock-Watt: IEC 62325-504 CLI Simulator")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    send_parser = subparsers.add_parser("send", help="Send a signed payload to a target URL")
    send_parser.add_argument("--payload", required=True, help="Path to the raw XML document")
    send_parser.add_argument("--url", required=True, help="Target HTTPS endpoint URL")
    send_parser.add_argument("--cert", required=True, help="Path to Mock-Watt client certificate (.pem)")
    send_parser.add_argument("--key", required=True, help="Path to Mock-Watt private key (.key)")
    send_parser.add_argument("--ca", required=False, help="Path to Root CA (optional)")
    send_parser.add_argument("--verb", default="created", help="IEC TC57 verb (default: created)")
    send_parser.add_argument("--noun", required=False, help="IEC TC57 noun (default: auto-detected from payload root element)")
    send_parser.add_argument("--store-request", action="store_true", help="Save the outbound SOAP envelope to data/outbound/")
    send_parser.add_argument("--store-response", action="store_true", help="Save the server response to data/inbound/")

    serve_parser = subparsers.add_parser("serve", help="Start the Mock-Watt gateway server")
    serve_parser.add_argument("--cert", required=True, help="Path to server certificate (.pem)")
    serve_parser.add_argument("--key", required=True, help="Path to server private key (.key)")
    serve_parser.add_argument("--ca", required=False, help="Path to Root CA for mTLS client verification (.pem)")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    serve_parser.add_argument("--port", type=int, default=8443, help="Bind port (default: 8443)")

    args = parser.parse_args()

    if args.command == "send":
        execute_request(
            payload_path=args.payload,
            target_url=args.url,
            cert_path=args.cert,
            key_path=args.key,
            ca_path=args.ca,
            verb=args.verb,
            noun=args.noun,
            store_request=args.store_request,
            store_response=args.store_response,
        )
    elif args.command == "serve":
        execute_serve(
            cert_path=args.cert,
            key_path=args.key,
            ca_path=args.ca,
            host=args.host,
            port=args.port,
        )
    else:
        parser.print_help()