from datetime import datetime, timezone

from lxml import etree

SOAP_ENV_NS = "http://www.w3.org/2003/05/soap-envelope"
IEC_MSG_NS = "http://iec.ch/TC57/2011/schema/message"
ACK_NS = "urn:iec62325.351:tc57wg16:451-1:acknowledgementdocument:8:0"

_NSMAP = {
    "soap": SOAP_ENV_NS,
    "mes": IEC_MSG_NS,
}

_SENDER_EIC = "10XXX-XXX----4-A"  # placeholder — configure per deployment


class ReplyBuilder:
    """
    Constructs SOAP 1.2 response envelopes for the IEC 62325-504 gateway.
    """

    @staticmethod
    def build_reply_message(
        noun: str,
        code: str,
        text: str,
        received_mrid: str = "",
        received_revision: str = "",
    ) -> bytes:
        """
        Builds a SOAP 1.2 mes:ResponseMessage envelope matching the TSO response structure.

        For OK responses the mes:Noun is always "Acknowledgement_MarketDocument" and a
        mes:Payload containing an ack:Acknowledgement_MarketDocument is appended.
        For NOK responses only mes:Reply/mes:Result and mes:Reply/mes:Text are included.

        :param noun: Echo of the request mes:Noun (unused in the header — kept for logging).
        :param code: Reply result — "OK" or "NOK".
        :param text: Human-readable description; included only on NOK.
        :param received_mrid: Original document identifier (from payload Identificador).
        :param received_revision: Original document revision (from payload Versao).
        :return: Serialised SOAP envelope as UTF-8 bytes.
        """
        envelope = etree.Element(f"{{{SOAP_ENV_NS}}}Envelope", nsmap=_NSMAP)
        body = etree.SubElement(envelope, f"{{{SOAP_ENV_NS}}}Body")

        response_message = etree.SubElement(body, f"{{{IEC_MSG_NS}}}ResponseMessage")

        mes_header = etree.SubElement(response_message, f"{{{IEC_MSG_NS}}}Header")
        etree.SubElement(mes_header, f"{{{IEC_MSG_NS}}}Verb").text = "reply"
        etree.SubElement(mes_header, f"{{{IEC_MSG_NS}}}Noun").text = "Acknowledgement_MarketDocument"
        etree.SubElement(mes_header, f"{{{IEC_MSG_NS}}}Context").text = "PRODUCTION"
        etree.SubElement(mes_header, f"{{{IEC_MSG_NS}}}Timestamp").text = (
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        )

        reply = etree.SubElement(response_message, f"{{{IEC_MSG_NS}}}Reply")
        etree.SubElement(reply, f"{{{IEC_MSG_NS}}}Result").text = code
        if code != "OK":
            etree.SubElement(reply, f"{{{IEC_MSG_NS}}}Text").text = text

        if code == "OK":
            ack_mrid = f"ACK_{received_mrid}" if received_mrid else (
                "ACK_" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")[:-3]
            )
            created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

            payload = etree.SubElement(response_message, f"{{{IEC_MSG_NS}}}Payload")
            ack_doc = etree.SubElement(
                payload,
                f"{{{ACK_NS}}}Acknowledgement_MarketDocument",
                nsmap={"ack": ACK_NS},
            )
            etree.SubElement(ack_doc, f"{{{ACK_NS}}}mRID").text = ack_mrid
            etree.SubElement(ack_doc, f"{{{ACK_NS}}}createdDateTime").text = created
            sender = etree.SubElement(ack_doc, f"{{{ACK_NS}}}sender_MarketParticipant.mRID")
            sender.set("codingScheme", "A01")
            sender.text = _SENDER_EIC
            etree.SubElement(
                ack_doc, f"{{{ACK_NS}}}sender_MarketParticipant.marketRole.type"
            ).text = "A04"
            receiver = etree.SubElement(
                ack_doc, f"{{{ACK_NS}}}receiver_MarketParticipant.mRID"
            )
            receiver.set("codingScheme", "A01")
            etree.SubElement(
                ack_doc, f"{{{ACK_NS}}}receiver_MarketParticipant.marketRole.type"
            ).text = "A11"
            etree.SubElement(
                ack_doc, f"{{{ACK_NS}}}received_MarketDocument.mRID"
            ).text = received_mrid
            etree.SubElement(
                ack_doc, f"{{{ACK_NS}}}received_MarketDocument.revisionNumber"
            ).text = received_revision
            reason = etree.SubElement(ack_doc, f"{{{ACK_NS}}}Reason")
            etree.SubElement(reason, f"{{{ACK_NS}}}code").text = "A01"
            etree.SubElement(reason, f"{{{ACK_NS}}}text").text = "Message fully accepted"

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
