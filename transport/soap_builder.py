from datetime import datetime, timezone

from lxml import etree


class SoapBuilder:
    """
    Constructs IEC 62325-504 compliant SOAP envelopes for B2B market communications.
    """

    # SOAP 1.2 namespace
    SOAP_ENV_NS = "http://www.w3.org/2003/05/soap-envelope"
    # IEC TC57 message framing namespace
    IEC_MSG_NS = "http://iec.ch/TC57/2011/schema/message"

    NSMAP = {
        'soap': SOAP_ENV_NS,
        'mes': IEC_MSG_NS,
    }

    @classmethod
    def build_request_message(cls, verb: str, noun: str, raw_payload: bytes) -> etree._Element:
        """
        Builds an unsigned IEC TC57 RequestMessage lxml element.

        The returned element is ready to be passed to SecurityEngine.sign_request_message()
        before wrapping in a SOAP envelope via wrap_in_envelope().

        :param verb: The IEC TC57 verb (e.g. "created", "changed", "deleted").
        :param noun: The IEC TC57 noun — typically the root element name of the business document.
        :param raw_payload: The unsigned business XML payload as bytes.
        :return: The mes:RequestMessage lxml element.
        """
        try:
            request_message = etree.Element(f"{{{cls.IEC_MSG_NS}}}RequestMessage", nsmap=cls.NSMAP)

            mes_header = etree.SubElement(request_message, f"{{{cls.IEC_MSG_NS}}}Header")
            etree.SubElement(mes_header, f"{{{cls.IEC_MSG_NS}}}Verb").text = verb
            etree.SubElement(mes_header, f"{{{cls.IEC_MSG_NS}}}Noun").text = noun
            etree.SubElement(mes_header, f"{{{cls.IEC_MSG_NS}}}Timestamp").text = (
                datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            )

            payload_node = etree.SubElement(request_message, f"{{{cls.IEC_MSG_NS}}}Payload")
            payload_node.append(etree.fromstring(raw_payload))

            return request_message

        except Exception as e:
            raise RuntimeError(f"Failed to build RequestMessage element: {e}")

    @classmethod
    def wrap_in_envelope(cls, request_message_el: etree._Element) -> bytes:
        """
        Wraps a RequestMessage element in a SOAP 1.2 Envelope and returns bytes.

        :param request_message_el: The (optionally signed) mes:RequestMessage element.
        :return: The fully constructed SOAP envelope as bytes, ready for HTTP POST.
        """
        envelope = etree.Element(f"{{{cls.SOAP_ENV_NS}}}Envelope", nsmap=cls.NSMAP)
        body = etree.SubElement(envelope, f"{{{cls.SOAP_ENV_NS}}}Body")
        body.append(request_message_el)
        return etree.tostring(
            envelope,
            encoding="utf-8",
            xml_declaration=True,
            pretty_print=False,
        )

    @classmethod
    def wrap_request_message(cls, verb: str, noun: str, raw_payload: bytes) -> bytes:
        """
        Convenience method: builds an unsigned RequestMessage and wraps it in a SOAP
        envelope in one step. Use this when no signing is required (e.g. tests).

        For signed outbound messages use build_request_message() + sign_request_message()
        + wrap_in_envelope() instead.

        :param verb: The IEC TC57 verb.
        :param noun: The IEC TC57 noun.
        :param raw_payload: The unsigned business XML payload as bytes.
        :return: The SOAP envelope as bytes.
        """
        return cls.wrap_in_envelope(cls.build_request_message(verb, noun, raw_payload))