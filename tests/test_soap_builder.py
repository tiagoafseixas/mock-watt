import pytest
from lxml import etree

from transport.soap_builder import SoapBuilder

SOAP_ENV_NS = "http://schemas.xmlsoap.org/soap/envelope/"
IEC_504_NS = "urn:iec62325.504:v1.0"

SAMPLE_SIGNED_PAYLOAD = b"""<Document xmlns="urn:test:cim"><ID>SIGNED-DOC-001</ID></Document>"""


class TestWrapPutMessage:
    def test_returns_bytes(self):
        result = SoapBuilder.wrap_put_message(SAMPLE_SIGNED_PAYLOAD)
        assert isinstance(result, bytes)

    def test_output_has_xml_declaration(self):
        result = SoapBuilder.wrap_put_message(SAMPLE_SIGNED_PAYLOAD)
        assert result.startswith(b"<?xml")

    def test_root_is_soap_envelope(self):
        result = SoapBuilder.wrap_put_message(SAMPLE_SIGNED_PAYLOAD)
        root = etree.fromstring(result)
        assert root.tag == f"{{{SOAP_ENV_NS}}}Envelope"

    def test_contains_soap_body(self):
        result = SoapBuilder.wrap_put_message(SAMPLE_SIGNED_PAYLOAD)
        root = etree.fromstring(result)
        body = root.find(f"{{{SOAP_ENV_NS}}}Body")
        assert body is not None

    def test_contains_soap_header(self):
        result = SoapBuilder.wrap_put_message(SAMPLE_SIGNED_PAYLOAD)
        root = etree.fromstring(result)
        header = root.find(f"{{{SOAP_ENV_NS}}}Header")
        assert header is not None

    def test_contains_put_message_operation(self):
        result = SoapBuilder.wrap_put_message(SAMPLE_SIGNED_PAYLOAD)
        root = etree.fromstring(result)
        put_message = root.find(f"{{{SOAP_ENV_NS}}}Body/{{{IEC_504_NS}}}PutMessage")
        assert put_message is not None

    def test_contains_request_node(self):
        result = SoapBuilder.wrap_put_message(SAMPLE_SIGNED_PAYLOAD)
        root = etree.fromstring(result)
        request = root.find(
            f"{{{SOAP_ENV_NS}}}Body/{{{IEC_504_NS}}}PutMessage/{{{IEC_504_NS}}}request"
        )
        assert request is not None

    def test_payload_embedded_as_xml_not_escaped(self):
        result = SoapBuilder.wrap_put_message(SAMPLE_SIGNED_PAYLOAD)
        root = etree.fromstring(result)
        request = root.find(
            f"{{{SOAP_ENV_NS}}}Body/{{{IEC_504_NS}}}PutMessage/{{{IEC_504_NS}}}request"
        )
        # The payload should be a real child element, not escaped text
        assert len(request) == 1
        assert request[0].tag == "{urn:test:cim}Document"

    def test_payload_content_preserved(self):
        result = SoapBuilder.wrap_put_message(SAMPLE_SIGNED_PAYLOAD)
        assert b"SIGNED-DOC-001" in result

    def test_raises_on_invalid_payload(self):
        with pytest.raises(RuntimeError):
            SoapBuilder.wrap_put_message(b"not valid xml")
