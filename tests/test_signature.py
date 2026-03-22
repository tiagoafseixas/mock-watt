import pytest
from pathlib import Path

from security.signature import SecurityEngine

CERTS_DIR = Path(__file__).parent.parent / "data" / "certs"
KEY_PATH = CERTS_DIR / "mock-watt.key"
CERT_PATH = CERTS_DIR / "mock-watt.pem"

SAMPLE_XML = b"""<Document xmlns="urn:test:cim"><ID>TEST-DOC-001</ID><Content>Hello IEC 62325</Content></Document>"""


@pytest.fixture
def engine():
    return SecurityEngine(key_path=str(KEY_PATH), cert_path=str(CERT_PATH))


class TestSecurityEngineInit:
    def test_loads_with_valid_paths(self):
        engine = SecurityEngine(key_path=str(KEY_PATH), cert_path=str(CERT_PATH))
        assert engine.private_key is not None
        assert engine.certificate is not None

    def test_raises_when_key_missing(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            SecurityEngine(
                key_path=str(tmp_path / "nonexistent.key"),
                cert_path=str(CERT_PATH),
            )

    def test_raises_when_cert_missing(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            SecurityEngine(
                key_path=str(KEY_PATH),
                cert_path=str(tmp_path / "nonexistent.pem"),
            )


class TestSignPayload:
    def test_returns_bytes(self, engine):
        result = engine.sign_payload(SAMPLE_XML)
        assert isinstance(result, bytes)

    def test_output_contains_signature_element(self, engine):
        result = engine.sign_payload(SAMPLE_XML)
        assert b"Signature" in result

    def test_output_is_valid_xml(self, engine):
        from lxml import etree
        result = engine.sign_payload(SAMPLE_XML)
        root = etree.fromstring(result)
        assert root is not None

    def test_original_content_preserved(self, engine):
        result = engine.sign_payload(SAMPLE_XML)
        assert b"TEST-DOC-001" in result

    def test_raises_on_invalid_xml(self, engine):
        with pytest.raises(RuntimeError):
            engine.sign_payload(b"this is not xml")


class TestVerifyPayload:
    def test_roundtrip_sign_then_verify(self, engine):
        signed = engine.sign_payload(SAMPLE_XML)
        verified = engine.verify_payload(signed)
        assert isinstance(verified, bytes)

    def test_verified_output_contains_original_content(self, engine):
        signed = engine.sign_payload(SAMPLE_XML)
        verified = engine.verify_payload(signed)
        assert b"TEST-DOC-001" in verified

    def test_raises_on_tampered_payload(self, engine):
        signed = engine.sign_payload(SAMPLE_XML)
        # Replace the document ID value to break the digest
        tampered = signed.replace(b"TEST-DOC-001", b"TAMPERED-9999")
        with pytest.raises(ValueError):
            engine.verify_payload(tampered)

    def test_raises_on_unsigned_xml(self, engine):
        with pytest.raises(ValueError):
            engine.verify_payload(SAMPLE_XML)
