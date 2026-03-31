import pytest
from lxml import etree
from pathlib import Path

from security.signature import SecurityEngine, DS_NS, _IEC_MSG_NS
from transport.soap_builder import SoapBuilder

CERTS_DIR = Path(__file__).parent.parent / "data" / "certs"
KEY_PATH = CERTS_DIR / "mock-watt.key"
CERT_PATH = CERTS_DIR / "mock-watt.pem"
CA_PATH = CERTS_DIR / "rootCA.pem"

SAMPLE_XML = b"<Document xmlns='urn:test:cim'><ID>INBOUND-DOC-001</ID></Document>"

pytestmark = pytest.mark.skipif(
    not KEY_PATH.exists() or not CERT_PATH.exists(),
    reason="PKI materials not found — run scripts/generate_certs.sh first",
)


@pytest.fixture(scope="module")
def engine():
    return SecurityEngine(key_path=str(KEY_PATH), cert_path=str(CERT_PATH))


@pytest.fixture(scope="module")
def signed_xml(engine):
    return engine.sign_payload(SAMPLE_XML)


class TestVerifyInboundValid:
    def test_roundtrip_returns_bytes(self, signed_xml):
        result = SecurityEngine.verify_inbound(signed_xml)
        assert isinstance(result, bytes)

    def test_roundtrip_preserves_content(self, signed_xml):
        result = SecurityEngine.verify_inbound(signed_xml)
        assert b"INBOUND-DOC-001" in result

    def test_with_ca_cert_passes_when_cert_signed_by_ca(self, signed_xml):
        if not CA_PATH.exists():
            pytest.skip("rootCA.pem not found")
        result = SecurityEngine.verify_inbound(signed_xml, ca_cert_path=str(CA_PATH))
        assert isinstance(result, bytes)


class TestSignRequestMessage:
    def test_signature_is_in_mes_header(self, engine):
        req_msg = SoapBuilder.build_request_message("created", "Document", SAMPLE_XML)
        engine.sign_request_message(req_msg)
        mes_header = req_msg.find(f"{{{_IEC_MSG_NS}}}Header")
        assert mes_header is not None
        sig = mes_header.find(f"{{{DS_NS}}}Signature")
        assert sig is not None, "ds:Signature must be inside mes:Header"

    def test_signature_not_in_payload(self, engine):
        req_msg = SoapBuilder.build_request_message("created", "Document", SAMPLE_XML)
        engine.sign_request_message(req_msg)
        payload = req_msg.find(f"{{{_IEC_MSG_NS}}}Payload")
        assert payload is not None
        sig = payload.find(f".//{{{DS_NS}}}Signature")
        assert sig is None, "ds:Signature must not be inside mes:Payload"

    def test_key_info_has_issuer_serial(self, engine):
        req_msg = SoapBuilder.build_request_message("created", "Document", SAMPLE_XML)
        engine.sign_request_message(req_msg)
        issuer_serial = req_msg.find(f".//{{{DS_NS}}}X509IssuerSerial")
        assert issuer_serial is not None
        issuer_name = issuer_serial.find(f"{{{DS_NS}}}X509IssuerName")
        serial_number = issuer_serial.find(f"{{{DS_NS}}}X509SerialNumber")
        assert issuer_name is not None and issuer_name.text
        assert serial_number is not None and serial_number.text

    def test_key_info_has_subject_name(self, engine):
        req_msg = SoapBuilder.build_request_message("created", "Document", SAMPLE_XML)
        engine.sign_request_message(req_msg)
        subj = req_msg.find(f".//{{{DS_NS}}}X509SubjectName")
        assert subj is not None and subj.text

    def test_key_info_still_has_certificate(self, engine):
        req_msg = SoapBuilder.build_request_message("created", "Document", SAMPLE_XML)
        engine.sign_request_message(req_msg)
        cert_el = req_msg.find(f".//{{{DS_NS}}}X509Certificate")
        assert cert_el is not None and cert_el.text

    def test_signed_request_message_verifies(self, engine):
        req_msg = SoapBuilder.build_request_message("created", "Document", SAMPLE_XML)
        engine.sign_request_message(req_msg)
        req_msg_bytes = etree.tostring(req_msg, encoding="utf-8")
        result = SecurityEngine.verify_inbound(req_msg_bytes)
        assert isinstance(result, bytes)

    def test_signed_request_message_content_preserved(self, engine):
        req_msg = SoapBuilder.build_request_message("created", "Document", SAMPLE_XML)
        engine.sign_request_message(req_msg)
        req_msg_bytes = etree.tostring(req_msg, encoding="utf-8")
        assert b"INBOUND-DOC-001" in req_msg_bytes

    def test_tampered_request_message_fails_verification(self, engine):
        req_msg = SoapBuilder.build_request_message("created", "Document", SAMPLE_XML)
        engine.sign_request_message(req_msg)
        req_msg_bytes = etree.tostring(req_msg, encoding="utf-8")
        tampered = req_msg_bytes.replace(b"INBOUND-DOC-001", b"TAMPERED-XXXX")
        with pytest.raises(ValueError, match="verification failed"):
            SecurityEngine.verify_inbound(tampered)


class TestVerifyInboundInvalid:
    def test_unsigned_xml_raises(self):
        with pytest.raises(ValueError, match="unsigned"):
            SecurityEngine.verify_inbound(SAMPLE_XML)

    def test_not_xml_raises(self):
        with pytest.raises(ValueError, match="not valid XML"):
            SecurityEngine.verify_inbound(b"not xml at all")

    def test_tampered_content_raises(self, signed_xml):
        tampered = signed_xml.replace(b"INBOUND-DOC-001", b"TAMPERED-XXXX")
        with pytest.raises(ValueError, match="verification failed"):
            SecurityEngine.verify_inbound(tampered)

    def test_truncated_signature_raises(self, signed_xml):
        # Remove the closing tags to corrupt the signature block
        truncated = signed_xml[: len(signed_xml) // 2]
        with pytest.raises(ValueError):
            SecurityEngine.verify_inbound(truncated)
