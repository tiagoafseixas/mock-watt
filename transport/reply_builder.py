from datetime import datetime, timezone

from lxml import etree

SOAP_ENV_NS = "http://www.w3.org/2003/05/soap-envelope"
IEC_MSG_NS = "http://iec.ch/TC57/2011/schema/message"

_NSMAP = {
    "soap": SOAP_ENV_NS,
    "mes": IEC_MSG_NS,
}


class ReplyBuilder:
    """
    Constructs SOAP 1.2 response envelopes for the IEC 62325-504 gateway.
    """

    @staticmethod
    def build_reply_message(noun: str, code: str, text: str) -> bytes:
        """
        Builds a SOAP 1.2 mes:ResponseMessage envelope matching the TSO response structure.

        :param noun: Echo of the request mes:Noun.
        :param code: Reply result — "OK" or "NOK".
        :param text: Human-readable description of the reply.
        :return: Serialised SOAP envelope as UTF-8 bytes.
        """
        envelope = etree.Element(f"{{{SOAP_ENV_NS}}}Envelope", nsmap=_NSMAP)
        body = etree.SubElement(envelope, f"{{{SOAP_ENV_NS}}}Body")

        response_message = etree.SubElement(body, f"{{{IEC_MSG_NS}}}ResponseMessage")

        mes_header = etree.SubElement(response_message, f"{{{IEC_MSG_NS}}}Header")
        etree.SubElement(mes_header, f"{{{IEC_MSG_NS}}}Verb").text = "reply"
        etree.SubElement(mes_header, f"{{{IEC_MSG_NS}}}Noun").text = noun
        etree.SubElement(mes_header, f"{{{IEC_MSG_NS}}}Context").text = "PRODUCTION"
        etree.SubElement(mes_header, f"{{{IEC_MSG_NS}}}Timestamp").text = (
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        )

        reply = etree.SubElement(response_message, f"{{{IEC_MSG_NS}}}Reply")
        etree.SubElement(reply, f"{{{IEC_MSG_NS}}}Result").text = code
        etree.SubElement(reply, f"{{{IEC_MSG_NS}}}Text").text = text

        return etree.tostring(
            envelope,
            encoding="utf-8",
            xml_declaration=True,
            pretty_print=False,
        )

    @staticmethod
    def build_soap_fault(code: str, reason: str) -> bytes:
        """
        Builds a SOAP 1.2 soap:Fault envelope for transport-level errors.

        :param code: SOAP fault code (e.g. "soap:Sender", "soap:Receiver").
        :param reason: Human-readable fault description.
        :return: Serialised SOAP fault envelope as UTF-8 bytes.
        """
        envelope = etree.Element(f"{{{SOAP_ENV_NS}}}Envelope", nsmap=_NSMAP)
        etree.SubElement(envelope, f"{{{SOAP_ENV_NS}}}Header")
        body = etree.SubElement(envelope, f"{{{SOAP_ENV_NS}}}Body")

        fault = etree.SubElement(body, f"{{{SOAP_ENV_NS}}}Fault")

        fault_code = etree.SubElement(fault, f"{{{SOAP_ENV_NS}}}Code")
        etree.SubElement(fault_code, f"{{{SOAP_ENV_NS}}}Value").text = code

        fault_reason = etree.SubElement(fault, f"{{{SOAP_ENV_NS}}}Reason")
        reason_text = etree.SubElement(fault_reason, f"{{{SOAP_ENV_NS}}}Text")
        reason_text.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
        reason_text.text = reason

        return etree.tostring(
            envelope,
            encoding="utf-8",
            xml_declaration=True,
            pretty_print=False,
        )
