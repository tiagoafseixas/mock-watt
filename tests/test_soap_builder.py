import pytest
from lxml import etree

from transport.soap_builder import SoapBuilder

SOAP_ENV_NS = "http://www.w3.org/2003/05/soap-envelope"
IEC_MSG_NS = "http://iec.ch/TC57/2011/schema/message"

SAMPLE_SIGNED_PAYLOAD = b"""<Document xmlns="urn:test:cim"><ID>SIGNED-DOC-001</ID></Document>"""
SAMPLE_VERB = "created"
SAMPLE_NOUN = "MensagemOferBandaFRR"


class TestWrapRequestMessage:
    def _build(self):
        return SoapBuilder.wrap_request_message(SAMPLE_VERB, SAMPLE_NOUN, SAMPLE_SIGNED_PAYLOAD)

    def test_returns_bytes(self):
        assert isinstance(self._build(), bytes)

    def test_output_has_xml_declaration(self):
        assert self._build().startswith(b"<?xml")

    def test_root_is_soap_envelope(self):
        root = etree.fromstring(self._build())
        assert root.tag == f"{{{SOAP_ENV_NS}}}Envelope"

    def test_contains_soap_header(self):
        root = etree.fromstring(self._build())
        assert root.find(f"{{{SOAP_ENV_NS}}}Header") is not None

    def test_contains_soap_body(self):
        root = etree.fromstring(self._build())
        assert root.find(f"{{{SOAP_ENV_NS}}}Body") is not None

    def test_contains_request_message(self):
        root = etree.fromstring(self._build())
        assert root.find(f"{{{SOAP_ENV_NS}}}Body/{{{IEC_MSG_NS}}}RequestMessage") is not None

    def test_contains_mes_header(self):
        root = etree.fromstring(self._build())
        mes_header = root.find(
            f"{{{SOAP_ENV_NS}}}Body/{{{IEC_MSG_NS}}}RequestMessage/{{{IEC_MSG_NS}}}Header"
        )
        assert mes_header is not None

    def test_mes_header_verb(self):
        root = etree.fromstring(self._build())
        verb = root.find(
            f"{{{SOAP_ENV_NS}}}Body/{{{IEC_MSG_NS}}}RequestMessage"
            f"/{{{IEC_MSG_NS}}}Header/{{{IEC_MSG_NS}}}Verb"
        )
        assert verb is not None
        assert verb.text == SAMPLE_VERB

    def test_mes_header_noun(self):
        root = etree.fromstring(self._build())
        noun = root.find(
            f"{{{SOAP_ENV_NS}}}Body/{{{IEC_MSG_NS}}}RequestMessage"
            f"/{{{IEC_MSG_NS}}}Header/{{{IEC_MSG_NS}}}Noun"
        )
        assert noun is not None
        assert noun.text == SAMPLE_NOUN

    def test_mes_header_timestamp_present(self):
        root = etree.fromstring(self._build())
        ts = root.find(
            f"{{{SOAP_ENV_NS}}}Body/{{{IEC_MSG_NS}}}RequestMessage"
            f"/{{{IEC_MSG_NS}}}Header/{{{IEC_MSG_NS}}}Timestamp"
        )
        assert ts is not None
        assert ts.text is not None

    def test_contains_payload_node(self):
        root = etree.fromstring(self._build())
        payload = root.find(
            f"{{{SOAP_ENV_NS}}}Body/{{{IEC_MSG_NS}}}RequestMessage/{{{IEC_MSG_NS}}}Payload"
        )
        assert payload is not None

    def test_payload_embedded_as_xml_not_escaped(self):
        root = etree.fromstring(self._build())
        payload = root.find(
            f"{{{SOAP_ENV_NS}}}Body/{{{IEC_MSG_NS}}}RequestMessage/{{{IEC_MSG_NS}}}Payload"
        )
        assert len(payload) == 1
        assert payload[0].tag == "{urn:test:cim}Document"

    def test_payload_content_preserved(self):
        assert b"SIGNED-DOC-001" in self._build()

    def test_raises_on_invalid_payload(self):
        with pytest.raises(RuntimeError):
            SoapBuilder.wrap_request_message(SAMPLE_VERB, SAMPLE_NOUN, b"not valid xml")
