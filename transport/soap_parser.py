from dataclasses import dataclass

from lxml import etree

SOAP_ENV_NS = "http://www.w3.org/2003/05/soap-envelope"
IEC_MSG_NS = "http://iec.ch/TC57/2011/schema/message"


class SoapParseError(Exception):
    """Raised when the SOAP envelope is malformed or violates the IEC TC57 structure."""
    pass


@dataclass
class ParsedRequest:
    verb: str
    noun: str
    timestamp: str
    payload_element: etree._Element
    request_message: etree._Element


class SoapParser:
    """
    Parses and structurally validates incoming SOAP 1.2 IEC TC57 RequestMessage envelopes.
    """

    @staticmethod
    def parse_request(raw_body: bytes) -> ParsedRequest:
        """
        Parses a raw HTTP body into a ParsedRequest.

        Validates (in order):
        1. Well-formed XML
        2. Root element is soap:Envelope (SOAP 1.2 namespace)
        3. soap:Body is present
        4. soap:Body contains exactly one child: mes:RequestMessage
        5. mes:Header is present with non-empty Verb, Noun, and Timestamp
        6. mes:Payload is present with exactly one XML child element

        :param raw_body: Raw HTTP request body bytes.
        :return: ParsedRequest dataclass with header fields and payload element.
        :raises SoapParseError: on any structural or namespace violation.
        """
        # 1. Parse XML
        try:
            root = etree.fromstring(raw_body)
        except etree.XMLSyntaxError as e:
            raise SoapParseError(f"Request body is not valid XML: {e}")

        # 2. Validate SOAP 1.2 Envelope namespace
        if root.tag != f"{{{SOAP_ENV_NS}}}Envelope":
            raise SoapParseError(
                f"Root element must be soap:Envelope "
                f"(ns: {SOAP_ENV_NS}), got '{root.tag}'"
            )

        # 3. soap:Body must be present
        body = root.find(f"{{{SOAP_ENV_NS}}}Body")
        if body is None:
            raise SoapParseError("soap:Envelope is missing soap:Body")

        # 4. soap:Body must contain mes:RequestMessage
        body_children = [c for c in body if not callable(c.tag)]
        if len(body_children) == 0:
            raise SoapParseError("soap:Body is empty")
        if len(body_children) > 1:
            raise SoapParseError(
                f"soap:Body must contain exactly one child element "
                f"(got {len(body_children)})"
            )

        request_message = body_children[0]
        if request_message.tag != f"{{{IEC_MSG_NS}}}RequestMessage":
            raise SoapParseError(
                f"soap:Body child must be mes:RequestMessage "
                f"(ns: {IEC_MSG_NS}), got '{request_message.tag}'"
            )

        # 5. mes:Header must be present with required fields
        mes_header = request_message.find(f"{{{IEC_MSG_NS}}}Header")
        if mes_header is None:
            raise SoapParseError("mes:RequestMessage is missing mes:Header")

        verb_el = mes_header.find(f"{{{IEC_MSG_NS}}}Verb")
        noun_el = mes_header.find(f"{{{IEC_MSG_NS}}}Noun")
        ts_el = mes_header.find(f"{{{IEC_MSG_NS}}}Timestamp")

        if verb_el is None or not (verb_el.text or "").strip():
            raise SoapParseError("mes:Header is missing or has empty mes:Verb")
        if noun_el is None or not (noun_el.text or "").strip():
            raise SoapParseError("mes:Header is missing or has empty mes:Noun")
        if ts_el is None or not (ts_el.text or "").strip():
            raise SoapParseError("mes:Header is missing or has empty mes:Timestamp")

        # 6. mes:Payload must be present with exactly one XML child
        payload_node = request_message.find(f"{{{IEC_MSG_NS}}}Payload")
        if payload_node is None:
            raise SoapParseError("mes:RequestMessage is missing mes:Payload")

        payload_children = list(payload_node)
        if len(payload_children) == 0:
            raise SoapParseError("mes:Payload is empty — no XML child element found")
        if len(payload_children) > 1:
            raise SoapParseError(
                f"mes:Payload must contain exactly one child element "
                f"(got {len(payload_children)})"
            )

        return ParsedRequest(
            verb=verb_el.text.strip(),
            noun=noun_el.text.strip(),
            timestamp=ts_el.text.strip(),
            payload_element=payload_children[0],
            request_message=request_message,
        )
