"""
Integration tests for the POST /ws504 endpoint.

mTLS is enforced at the Uvicorn layer and is not testable via TestClient.
These tests cover the application logic gates:
  Gate 1 — Content-Type, SOAP structure, IEC TC57 header, XML-DSig
  Gate 2 — XSD schema dispatch and validation
"""
import pytest
from pathlib import Path
from lxml import etree
from starlette.testclient import TestClient

import server.app as app_module
from server.app import app
from server.schema_registry import SchemaRegistry
from security.signature import SecurityEngine
from transport.soap_builder import SoapBuilder

CERTS_DIR = Path(__file__).parent.parent / "data" / "certs"
KEY_PATH = CERTS_DIR / "mock-watt.key"
CERT_PATH = CERTS_DIR / "mock-watt.pem"

SOAP_ENV_NS = "http://www.w3.org/2003/05/soap-envelope"
IEC_MSG_NS = "http://iec.ch/TC57/2011/schema/message"

SOAP_XML_CONTENT_TYPE = "application/soap+xml; charset=utf-8"

_HAS_CERTS = KEY_PATH.exists() and CERT_PATH.exists()

# Minimal XSD for test payloads
_DOCUMENT_XSD = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:element name="Document">
    <xs:complexType>
      <xs:sequence>
        <xs:element name="ID" type="xs:string"/>
      </xs:sequence>
    </xs:complexType>
  </xs:element>
</xs:schema>
"""

_VALID_PAYLOAD_XML = b"<Document><ID>DOC-001</ID></Document>"
_INVALID_PAYLOAD_XML = b"<Document><WrongField>oops</WrongField></Document>"


@pytest.fixture(scope="module")
def engine():
    if not _HAS_CERTS:
        pytest.skip("PKI materials not found — run scripts/generate_certs.sh first")
    return SecurityEngine(key_path=str(KEY_PATH), cert_path=str(CERT_PATH))


@pytest.fixture
def schema_registry(tmp_path):
    (tmp_path / "document.xsd").write_bytes(_DOCUMENT_XSD)
    return SchemaRegistry(str(tmp_path))


@pytest.fixture(autouse=True)
def configure_app(schema_registry, monkeypatch):
    """Inject a test registry and disable CA validation for every test."""
    monkeypatch.setattr(app_module, "_registry", schema_registry)
    monkeypatch.setattr(app_module, "_ca_cert_path", None)


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


def _build_envelope(verb="created", noun="Document", payload_bytes=None) -> bytes:
    """Build a raw (unsigned) SOAP envelope."""
    nsmap = {"soap": SOAP_ENV_NS, "mes": IEC_MSG_NS}
    envelope = etree.Element(f"{{{SOAP_ENV_NS}}}Envelope", nsmap=nsmap)
    etree.SubElement(envelope, f"{{{SOAP_ENV_NS}}}Header")
    body = etree.SubElement(envelope, f"{{{SOAP_ENV_NS}}}Body")
    req = etree.SubElement(body, f"{{{IEC_MSG_NS}}}RequestMessage")
    hdr = etree.SubElement(req, f"{{{IEC_MSG_NS}}}Header")
    etree.SubElement(hdr, f"{{{IEC_MSG_NS}}}Verb").text = verb
    etree.SubElement(hdr, f"{{{IEC_MSG_NS}}}Noun").text = noun
    etree.SubElement(hdr, f"{{{IEC_MSG_NS}}}Timestamp").text = "2026-01-01T00:00:00Z"
    if payload_bytes:
        pnode = etree.SubElement(req, f"{{{IEC_MSG_NS}}}Payload")
        pnode.append(etree.fromstring(payload_bytes))
    return etree.tostring(envelope, xml_declaration=True, encoding="utf-8")


def _signed_envelope(engine, payload_xml=_VALID_PAYLOAD_XML, noun="Document") -> bytes:
    """Build a fully signed SOAP envelope using the test PKI."""
    req_msg = SoapBuilder.build_request_message("created", noun, payload_xml)
    engine.sign_request_message(req_msg)
    return SoapBuilder.wrap_in_envelope(req_msg)


def _parse_response(response_bytes: bytes):
    return etree.fromstring(response_bytes)


# --------------------------------------------------------------------------- #
# Gate 1a — Content-Type                                                       #
# --------------------------------------------------------------------------- #

class TestContentTypeGate:
    def test_missing_content_type_returns_fault(self, client):
        resp = client.post("/ws504", content=b"<x/>")
        assert resp.status_code == 400
        assert b"soap:Fault" in resp.content

    def test_wrong_content_type_returns_fault(self, client):
        resp = client.post(
            "/ws504",
            content=b"<x/>",
            headers={"content-type": "text/xml"},
        )
        assert resp.status_code == 400
        assert b"soap:Fault" in resp.content

    def test_correct_content_type_passes_gate(self, client, engine):
        # With a valid signed envelope this should not fault on Content-Type
        resp = client.post(
            "/ws504",
            content=_signed_envelope(engine),
            headers={"content-type": SOAP_XML_CONTENT_TYPE},
        )
        assert b"soap:Fault" not in resp.content or resp.status_code != 400


# --------------------------------------------------------------------------- #
# Gate 1b — SOAP structure                                                     #
# --------------------------------------------------------------------------- #

class TestSoapStructureGate:
    def test_empty_body_returns_fault(self, client):
        resp = client.post(
            "/ws504",
            content=b"",
            headers={"content-type": SOAP_XML_CONTENT_TYPE},
        )
        assert resp.status_code == 400
        assert b"soap:Fault" in resp.content

    def test_invalid_xml_returns_fault(self, client):
        resp = client.post(
            "/ws504",
            content=b"not xml",
            headers={"content-type": SOAP_XML_CONTENT_TYPE},
        )
        assert resp.status_code == 400
        assert b"soap:Fault" in resp.content

    def test_wrong_soap_namespace_returns_fault(self, client):
        bad_envelope = b"""<?xml version='1.0'?>
        <soap:Envelope xmlns:soap='http://schemas.xmlsoap.org/soap/envelope/'>
            <soap:Body/>
        </soap:Envelope>"""
        resp = client.post(
            "/ws504",
            content=bad_envelope,
            headers={"content-type": SOAP_XML_CONTENT_TYPE},
        )
        assert resp.status_code == 400
        assert b"soap:Fault" in resp.content

    def test_missing_request_message_returns_fault(self, client):
        nsmap = {"soap": SOAP_ENV_NS}
        envelope = etree.Element(f"{{{SOAP_ENV_NS}}}Envelope", nsmap=nsmap)
        etree.SubElement(envelope, f"{{{SOAP_ENV_NS}}}Body")
        raw = etree.tostring(envelope, xml_declaration=True, encoding="utf-8")
        resp = client.post(
            "/ws504",
            content=raw,
            headers={"content-type": SOAP_XML_CONTENT_TYPE},
        )
        assert resp.status_code == 400
        assert b"soap:Fault" in resp.content

    def test_missing_iec_header_returns_fault(self, client):
        raw = _build_envelope(payload_bytes=_VALID_PAYLOAD_XML)
        # Reconstruct without header
        nsmap = {"soap": SOAP_ENV_NS, "mes": IEC_MSG_NS}
        envelope = etree.Element(f"{{{SOAP_ENV_NS}}}Envelope", nsmap=nsmap)
        body = etree.SubElement(envelope, f"{{{SOAP_ENV_NS}}}Body")
        req = etree.SubElement(body, f"{{{IEC_MSG_NS}}}RequestMessage")
        # No mes:Header added
        pnode = etree.SubElement(req, f"{{{IEC_MSG_NS}}}Payload")
        pnode.append(etree.fromstring(_VALID_PAYLOAD_XML))
        raw = etree.tostring(envelope, xml_declaration=True, encoding="utf-8")
        resp = client.post(
            "/ws504",
            content=raw,
            headers={"content-type": SOAP_XML_CONTENT_TYPE},
        )
        assert resp.status_code == 400
        assert b"soap:Fault" in resp.content


# --------------------------------------------------------------------------- #
# Gate 1c — XML-DSig verification                                              #
# --------------------------------------------------------------------------- #

class TestSignatureGate:
    def test_unsigned_payload_returns_fault(self, client):
        raw = _build_envelope(payload_bytes=_VALID_PAYLOAD_XML)
        resp = client.post(
            "/ws504",
            content=raw,
            headers={"content-type": SOAP_XML_CONTENT_TYPE},
        )
        assert resp.status_code == 400
        assert b"soap:Fault" in resp.content

    def test_tampered_signature_returns_fault(self, client, engine):
        signed_envelope = _signed_envelope(engine)
        # Corrupt the DigestValue to break the signature
        tampered = signed_envelope.replace(b"DOC-001", b"TAMPERED")
        resp = client.post(
            "/ws504",
            content=tampered,
            headers={"content-type": SOAP_XML_CONTENT_TYPE},
        )
        assert resp.status_code == 400
        assert b"soap:Fault" in resp.content


# --------------------------------------------------------------------------- #
# Gate 2 — Schema validation                                                   #
# --------------------------------------------------------------------------- #

class TestSchemaGate:
    def test_no_schema_for_root_element_returns_nok(self, client, engine):
        # Sign a payload whose root element has no registered schema
        payload = b"<UnknownDocument><ID>X</ID></UnknownDocument>"
        envelope = _signed_envelope(engine, payload_xml=payload, noun="UnknownDocument")
        resp = client.post(
            "/ws504",
            content=envelope,
            headers={"content-type": SOAP_XML_CONTENT_TYPE},
        )
        assert resp.status_code == 200
        assert b"NOK" in resp.content

    def test_invalid_payload_against_schema_returns_nok(self, client, engine):
        envelope = _signed_envelope(engine, payload_xml=_INVALID_PAYLOAD_XML)
        resp = client.post(
            "/ws504",
            content=envelope,
            headers={"content-type": SOAP_XML_CONTENT_TYPE},
        )
        assert resp.status_code == 200
        assert b"NOK" in resp.content

    def test_valid_payload_returns_ok(self, client, engine):
        envelope = _signed_envelope(engine)
        resp = client.post(
            "/ws504",
            content=envelope,
            headers={"content-type": SOAP_XML_CONTENT_TYPE},
        )
        assert resp.status_code == 200
        assert b"OK" in resp.content
        assert b"NOK" not in resp.content

    def test_ok_response_echoes_noun(self, client, engine):
        envelope = _signed_envelope(engine)
        resp = client.post(
            "/ws504",
            content=envelope,
            headers={"content-type": SOAP_XML_CONTENT_TYPE},
        )
        root = _parse_response(resp.content)
        noun = root.find(
            f"{{{SOAP_ENV_NS}}}Body"
            f"/{{{IEC_MSG_NS}}}ReplyMessage"
            f"/{{{IEC_MSG_NS}}}Header"
            f"/{{{IEC_MSG_NS}}}Noun"
        )
        assert noun is not None
        assert noun.text == "Document"

    def test_ok_response_is_soap_xml(self, client, engine):
        envelope = _signed_envelope(engine)
        resp = client.post(
            "/ws504",
            content=envelope,
            headers={"content-type": SOAP_XML_CONTENT_TYPE},
        )
        assert "application/soap+xml" in resp.headers["content-type"]
