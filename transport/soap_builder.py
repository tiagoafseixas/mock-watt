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
    def wrap_request_message(cls, verb: str, noun: str, signed_payload: bytes) -> bytes:
        """
        Wraps a signed CIM XML payload into a SOAP 1.2 + IEC TC57 RequestMessage envelope.

        :param verb: The IEC TC57 verb (e.g. "created", "changed", "deleted").
        :param noun: The IEC TC57 noun — typically the root element name of the business document.
        :param signed_payload: The digitally signed XML payload as bytes.
        :return: The fully constructed SOAP envelope as bytes, ready for HTTP POST.
        """
        try:
            # 1. Build the SOAP 1.2 Envelope
            envelope = etree.Element(f"{{{cls.SOAP_ENV_NS}}}Envelope", nsmap=cls.NSMAP)
            etree.SubElement(envelope, f"{{{cls.SOAP_ENV_NS}}}Header")
            body = etree.SubElement(envelope, f"{{{cls.SOAP_ENV_NS}}}Body")

            # 2. IEC TC57 RequestMessage with Header (Verb / Noun / Timestamp)
            request_message = etree.SubElement(body, f"{{{cls.IEC_MSG_NS}}}RequestMessage")

            mes_header = etree.SubElement(request_message, f"{{{cls.IEC_MSG_NS}}}Header")
            etree.SubElement(mes_header, f"{{{cls.IEC_MSG_NS}}}Verb").text = verb
            etree.SubElement(mes_header, f"{{{cls.IEC_MSG_NS}}}Noun").text = noun
            etree.SubElement(mes_header, f"{{{cls.IEC_MSG_NS}}}Timestamp").text = (
                datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            )

            # 3. Inject the signed payload into <mes:Payload> as real XML nodes
            # Note: pretty_print=False is CRITICAL — must not alter whitespace of the
            # already-signed inner payload, or the signature will be invalidated.
            payload_node = etree.SubElement(request_message, f"{{{cls.IEC_MSG_NS}}}Payload")
            payload_node.append(etree.fromstring(signed_payload))

            # 4. Return the finalised envelope
            return etree.tostring(
                envelope,
                encoding="utf-8",
                xml_declaration=True,
                pretty_print=False,
            )

        except Exception as e:
            raise RuntimeError(f"Failed to construct the SOAP envelope: {str(e)}")