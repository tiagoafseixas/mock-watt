from lxml import etree

class SoapBuilder:
    """
    Constructs IEC 62325-504 compliant SOAP envelopes for B2B market communications.
    """
    
    # Standard Namespaces for IEC 62325-504
    SOAP_ENV_NS = "http://schemas.xmlsoap.org/soap/envelope/"
    IEC_504_NS = "urn:iec62325.504:v1.0"
    
    NSMAP = {
        'soapenv': SOAP_ENV_NS,
        'urn': IEC_504_NS
    }

    @classmethod
    def wrap_put_message(cls, signed_payload: bytes) -> bytes:
        """
        Wraps a signed CIM XML payload into a standard 504 <PutMessage> SOAP envelope.
        
        :param signed_payload: The digitally signed XML payload as bytes.
        :return: The fully constructed SOAP envelope as bytes, ready for HTTP POST.
        """
        try:
            # 1. Create the base SOAP Envelope and Header
            envelope = etree.Element(f"{{{cls.SOAP_ENV_NS}}}Envelope", nsmap=cls.NSMAP)
            header = etree.SubElement(envelope, f"{{{cls.SOAP_ENV_NS}}}Header")
            body = etree.SubElement(envelope, f"{{{cls.SOAP_ENV_NS}}}Body")
            
            # 2. Create the IEC 62325-504 PutMessage Operation structure
            put_message = etree.SubElement(body, f"{{{cls.IEC_504_NS}}}PutMessage")
            request_node = etree.SubElement(put_message, f"{{{cls.IEC_504_NS}}}request")
            
            # 3. Parse the signed payload back into an lxml Element
            # We do this to append it as actual XML nodes, not as an escaped string.
            payload_element = etree.fromstring(signed_payload)
            
            # 4. Inject the signed payload into the <request> node
            request_node.append(payload_element)
            
            # 5. Return the finalized SOAP message
            # Note: pretty_print=False is CRITICAL here so we do not alter 
            # the whitespace of the already-signed inner payload.
            return etree.tostring(
                envelope, 
                encoding="utf-8", 
                xml_declaration=True, 
                pretty_print=False
            )
            
        except Exception as e:
            raise RuntimeError(f"Failed to construct the SOAP envelope: {str(e)}")