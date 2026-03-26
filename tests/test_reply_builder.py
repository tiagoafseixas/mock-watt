import pytest
from lxml import etree

from transport.reply_builder import ReplyBuilder

SOAP_ENV_NS = "http://www.w3.org/2003/05/soap-envelope"
IEC_MSG_NS = "http://iec.ch/TC57/2011/schema/message"


class TestBuildReplyMessage:
    def _build(self, noun="Document", code="OK", text="Accepted."):
        return ReplyBuilder.build_reply_message(noun, code, text)

    def test_returns_bytes(self):
        assert isinstance(self._build(), bytes)

    def test_has_xml_declaration(self):
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

    def test_contains_reply_message(self):
        root = etree.fromstring(self._build())
        body = root.find(f"{{{SOAP_ENV_NS}}}Body")
        assert body.find(f"{{{IEC_MSG_NS}}}ReplyMessage") is not None

    def test_mes_header_verb_is_reply(self):
        root = etree.fromstring(self._build())
        verb = root.find(
            f"{{{SOAP_ENV_NS}}}Body"
            f"/{{{IEC_MSG_NS}}}ReplyMessage"
            f"/{{{IEC_MSG_NS}}}Header"
            f"/{{{IEC_MSG_NS}}}Verb"
        )
        assert verb is not None
        assert verb.text == "reply"

    def test_mes_header_noun_echoed(self):
        root = etree.fromstring(self._build(noun="MensagemOferBandaFRR"))
        noun = root.find(
            f"{{{SOAP_ENV_NS}}}Body"
            f"/{{{IEC_MSG_NS}}}ReplyMessage"
            f"/{{{IEC_MSG_NS}}}Header"
            f"/{{{IEC_MSG_NS}}}Noun"
        )
        assert noun is not None
        assert noun.text == "MensagemOferBandaFRR"

    def test_mes_header_timestamp_present(self):
        root = etree.fromstring(self._build())
        ts = root.find(
            f"{{{SOAP_ENV_NS}}}Body"
            f"/{{{IEC_MSG_NS}}}ReplyMessage"
            f"/{{{IEC_MSG_NS}}}Header"
            f"/{{{IEC_MSG_NS}}}Timestamp"
        )
        assert ts is not None
        assert ts.text is not None

    def test_reply_code_ok(self):
        root = etree.fromstring(self._build(code="OK"))
        code = root.find(
            f"{{{SOAP_ENV_NS}}}Body"
            f"/{{{IEC_MSG_NS}}}ReplyMessage"
            f"/{{{IEC_MSG_NS}}}Reply"
            f"/{{{IEC_MSG_NS}}}Code"
        )
        assert code is not None
        assert code.text == "OK"

    def test_reply_code_nok(self):
        root = etree.fromstring(self._build(code="NOK"))
        code = root.find(
            f"{{{SOAP_ENV_NS}}}Body"
            f"/{{{IEC_MSG_NS}}}ReplyMessage"
            f"/{{{IEC_MSG_NS}}}Reply"
            f"/{{{IEC_MSG_NS}}}Code"
        )
        assert code.text == "NOK"

    def test_reply_text_present(self):
        root = etree.fromstring(self._build(text="Schema validation failed."))
        text = root.find(
            f"{{{SOAP_ENV_NS}}}Body"
            f"/{{{IEC_MSG_NS}}}ReplyMessage"
            f"/{{{IEC_MSG_NS}}}Reply"
            f"/{{{IEC_MSG_NS}}}Text"
        )
        assert text is not None
        assert text.text == "Schema validation failed."


class TestBuildSoapFault:
    def _build(self, code="soap:Sender", reason="Bad request."):
        return ReplyBuilder.build_soap_fault(code, reason)

    def test_returns_bytes(self):
        assert isinstance(self._build(), bytes)

    def test_has_xml_declaration(self):
        assert self._build().startswith(b"<?xml")

    def test_root_is_soap_envelope(self):
        root = etree.fromstring(self._build())
        assert root.tag == f"{{{SOAP_ENV_NS}}}Envelope"

    def test_contains_fault(self):
        root = etree.fromstring(self._build())
        body = root.find(f"{{{SOAP_ENV_NS}}}Body")
        assert body.find(f"{{{SOAP_ENV_NS}}}Fault") is not None

    def test_fault_code_value(self):
        root = etree.fromstring(self._build(code="soap:Sender"))
        code_value = root.find(
            f"{{{SOAP_ENV_NS}}}Body"
            f"/{{{SOAP_ENV_NS}}}Fault"
            f"/{{{SOAP_ENV_NS}}}Code"
            f"/{{{SOAP_ENV_NS}}}Value"
        )
        assert code_value is not None
        assert code_value.text == "soap:Sender"

    def test_fault_reason_text(self):
        root = etree.fromstring(self._build(reason="Invalid envelope."))
        reason_text = root.find(
            f"{{{SOAP_ENV_NS}}}Body"
            f"/{{{SOAP_ENV_NS}}}Fault"
            f"/{{{SOAP_ENV_NS}}}Reason"
            f"/{{{SOAP_ENV_NS}}}Text"
        )
        assert reason_text is not None
        assert reason_text.text == "Invalid envelope."

    def test_fault_reason_lang_attribute(self):
        root = etree.fromstring(self._build())
        reason_text = root.find(
            f"{{{SOAP_ENV_NS}}}Body"
            f"/{{{SOAP_ENV_NS}}}Fault"
            f"/{{{SOAP_ENV_NS}}}Reason"
            f"/{{{SOAP_ENV_NS}}}Text"
        )
        lang = reason_text.get("{http://www.w3.org/XML/1998/namespace}lang")
        assert lang == "en"
