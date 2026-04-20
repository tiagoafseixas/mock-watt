import pytest
from lxml import etree

from transport.soap_parser import SoapParser, SoapParseError

SOAP_ENV_NS = "http://www.w3.org/2003/05/soap-envelope"
IEC_MSG_NS = "http://iec.ch/TC57/2011/schema/message"

SAMPLE_PAYLOAD = b"<Document xmlns='urn:test:cim'><ID>DOC-001</ID></Document>"


def _build_envelope(
    verb="created",
    noun="Document",
    timestamp="2026-01-01T00:00:00Z",
    payload_xml=SAMPLE_PAYLOAD,
    soap_ns=SOAP_ENV_NS,
    msg_ns=IEC_MSG_NS,
    include_header=True,
    include_payload=True,
) -> bytes:
    """Helper to build a minimal SOAP envelope for test parametrisation."""
    nsmap = {"soap": soap_ns, "mes": msg_ns}
    envelope = etree.Element(f"{{{soap_ns}}}Envelope", nsmap=nsmap)
    etree.SubElement(envelope, f"{{{soap_ns}}}Header")
    body = etree.SubElement(envelope, f"{{{soap_ns}}}Body")
    req = etree.SubElement(body, f"{{{msg_ns}}}RequestMessage")

    if include_header:
        hdr = etree.SubElement(req, f"{{{msg_ns}}}Header")
        if verb is not None:
            etree.SubElement(hdr, f"{{{msg_ns}}}Verb").text = verb
        if noun is not None:
            etree.SubElement(hdr, f"{{{msg_ns}}}Noun").text = noun
        if timestamp is not None:
            etree.SubElement(hdr, f"{{{msg_ns}}}Timestamp").text = timestamp

    if include_payload:
        payload_node = etree.SubElement(req, f"{{{msg_ns}}}Payload")
        payload_node.append(etree.fromstring(payload_xml))

    return etree.tostring(envelope, xml_declaration=True, encoding="utf-8")


class TestParseRequestValid:
    def test_returns_parsed_request(self):
        result = SoapParser.parse_request(_build_envelope())
        assert result is not None

    def test_verb_extracted(self):
        result = SoapParser.parse_request(_build_envelope(verb="changed"))
        assert result.verb == "changed"

    def test_noun_extracted(self):
        result = SoapParser.parse_request(_build_envelope(noun="MensagemOferBandaFRR"))
        assert result.noun == "MensagemOferBandaFRR"

    def test_timestamp_extracted(self):
        result = SoapParser.parse_request(_build_envelope(timestamp="2026-03-23T11:00:00Z"))
        assert result.timestamp == "2026-03-23T11:00:00Z"

    def test_payload_element_is_lxml_element(self):
        result = SoapParser.parse_request(_build_envelope())
        assert isinstance(result.payload_element, etree._Element)

    def test_payload_element_localname(self):
        result = SoapParser.parse_request(_build_envelope())
        assert etree.QName(result.payload_element).localname == "Document"

    def test_request_message_is_lxml_element(self):
        result = SoapParser.parse_request(_build_envelope())
        assert isinstance(result.request_message, etree._Element)

    def test_request_message_localname(self):
        result = SoapParser.parse_request(_build_envelope())
        assert etree.QName(result.request_message).localname == "RequestMessage"

    def test_verb_and_noun_stripped_of_whitespace(self):
        raw = _build_envelope(verb="  created  ", noun="  Document  ")
        result = SoapParser.parse_request(raw)
        assert result.verb == "created"
        assert result.noun == "Document"


class TestParseRequestInvalidXml:
    def test_not_xml_raises(self):
        with pytest.raises(SoapParseError, match="not valid XML"):
            SoapParser.parse_request(b"this is not xml")

    def test_empty_body_raises(self):
        with pytest.raises(SoapParseError):
            SoapParser.parse_request(b"")


class TestParseRequestEnvelopeStructure:
    def test_wrong_soap_namespace_raises(self):
        raw = _build_envelope(soap_ns="http://schemas.xmlsoap.org/soap/envelope/")
        with pytest.raises(SoapParseError, match="soap:Envelope"):
            SoapParser.parse_request(raw)

    def test_non_envelope_root_raises(self):
        with pytest.raises(SoapParseError, match="soap:Envelope"):
            SoapParser.parse_request(b"<Root><Child/></Root>")

    def test_missing_body_raises(self):
        nsmap = {"soap": SOAP_ENV_NS}
        envelope = etree.Element(f"{{{SOAP_ENV_NS}}}Envelope", nsmap=nsmap)
        raw = etree.tostring(envelope, xml_declaration=True, encoding="utf-8")
        with pytest.raises(SoapParseError, match="soap:Body"):
            SoapParser.parse_request(raw)

    def test_empty_body_raises(self):
        nsmap = {"soap": SOAP_ENV_NS}
        envelope = etree.Element(f"{{{SOAP_ENV_NS}}}Envelope", nsmap=nsmap)
        etree.SubElement(envelope, f"{{{SOAP_ENV_NS}}}Body")
        raw = etree.tostring(envelope, xml_declaration=True, encoding="utf-8")
        with pytest.raises(SoapParseError, match="empty"):
            SoapParser.parse_request(raw)

    def test_wrong_body_child_raises(self):
        nsmap = {"soap": SOAP_ENV_NS}
        envelope = etree.Element(f"{{{SOAP_ENV_NS}}}Envelope", nsmap=nsmap)
        body = etree.SubElement(envelope, f"{{{SOAP_ENV_NS}}}Body")
        etree.SubElement(body, "WrongElement")
        raw = etree.tostring(envelope, xml_declaration=True, encoding="utf-8")
        with pytest.raises(SoapParseError, match="mes:RequestMessage"):
            SoapParser.parse_request(raw)

    def test_multiple_body_children_raises(self):
        nsmap = {"soap": SOAP_ENV_NS, "mes": IEC_MSG_NS}
        envelope = etree.Element(f"{{{SOAP_ENV_NS}}}Envelope", nsmap=nsmap)
        body = etree.SubElement(envelope, f"{{{SOAP_ENV_NS}}}Body")
        etree.SubElement(body, f"{{{IEC_MSG_NS}}}RequestMessage")
        etree.SubElement(body, f"{{{IEC_MSG_NS}}}RequestMessage")
        raw = etree.tostring(envelope, xml_declaration=True, encoding="utf-8")
        with pytest.raises(SoapParseError, match="exactly one"):
            SoapParser.parse_request(raw)


class TestParseRequestHeader:
    def test_missing_header_raises(self):
        raw = _build_envelope(include_header=False)
        with pytest.raises(SoapParseError, match="mes:Header"):
            SoapParser.parse_request(raw)

    def test_missing_verb_raises(self):
        raw = _build_envelope(verb=None)
        with pytest.raises(SoapParseError, match="mes:Verb"):
            SoapParser.parse_request(raw)

    def test_missing_noun_raises(self):
        raw = _build_envelope(noun=None)
        with pytest.raises(SoapParseError, match="mes:Noun"):
            SoapParser.parse_request(raw)

    def test_missing_timestamp_raises(self):
        raw = _build_envelope(timestamp=None)
        with pytest.raises(SoapParseError, match="mes:Timestamp"):
            SoapParser.parse_request(raw)

    def test_empty_verb_raises(self):
        raw = _build_envelope(verb="   ")
        with pytest.raises(SoapParseError, match="mes:Verb"):
            SoapParser.parse_request(raw)

    def test_empty_noun_raises(self):
        raw = _build_envelope(noun="")
        with pytest.raises(SoapParseError, match="mes:Noun"):
            SoapParser.parse_request(raw)


class TestParseRequestPayload:
    def test_missing_payload_raises(self):
        raw = _build_envelope(include_payload=False)
        with pytest.raises(SoapParseError, match="mes:Payload"):
            SoapParser.parse_request(raw)

    def test_empty_payload_raises(self):
        nsmap = {"soap": SOAP_ENV_NS, "mes": IEC_MSG_NS}
        envelope = etree.Element(f"{{{SOAP_ENV_NS}}}Envelope", nsmap=nsmap)
        body = etree.SubElement(envelope, f"{{{SOAP_ENV_NS}}}Body")
        req = etree.SubElement(body, f"{{{IEC_MSG_NS}}}RequestMessage")
        hdr = etree.SubElement(req, f"{{{IEC_MSG_NS}}}Header")
        etree.SubElement(hdr, f"{{{IEC_MSG_NS}}}Verb").text = "created"
        etree.SubElement(hdr, f"{{{IEC_MSG_NS}}}Noun").text = "Document"
        etree.SubElement(hdr, f"{{{IEC_MSG_NS}}}Timestamp").text = "2026-01-01T00:00:00Z"
        etree.SubElement(req, f"{{{IEC_MSG_NS}}}Payload")  # empty payload
        raw = etree.tostring(envelope, xml_declaration=True, encoding="utf-8")
        with pytest.raises(SoapParseError, match="empty"):
            SoapParser.parse_request(raw)

    def test_multiple_payload_children_raises(self):
        extra = (
            b"<Document xmlns='urn:test:cim'><ID>DOC-001</ID></Document>"
            b"<Document xmlns='urn:test:cim'><ID>DOC-002</ID></Document>"
        )
        nsmap = {"soap": SOAP_ENV_NS, "mes": IEC_MSG_NS}
        envelope = etree.Element(f"{{{SOAP_ENV_NS}}}Envelope", nsmap=nsmap)
        body = etree.SubElement(envelope, f"{{{SOAP_ENV_NS}}}Body")
        req = etree.SubElement(body, f"{{{IEC_MSG_NS}}}RequestMessage")
        hdr = etree.SubElement(req, f"{{{IEC_MSG_NS}}}Header")
        etree.SubElement(hdr, f"{{{IEC_MSG_NS}}}Verb").text = "created"
        etree.SubElement(hdr, f"{{{IEC_MSG_NS}}}Noun").text = "Document"
        etree.SubElement(hdr, f"{{{IEC_MSG_NS}}}Timestamp").text = "2026-01-01T00:00:00Z"
        payload_node = etree.SubElement(req, f"{{{IEC_MSG_NS}}}Payload")
        payload_node.append(etree.fromstring(b"<Document xmlns='urn:test:cim'><ID>DOC-001</ID></Document>"))
        payload_node.append(etree.fromstring(b"<Document xmlns='urn:test:cim'><ID>DOC-002</ID></Document>"))
        raw = etree.tostring(envelope, xml_declaration=True, encoding="utf-8")
        with pytest.raises(SoapParseError, match="exactly one"):
            SoapParser.parse_request(raw)
