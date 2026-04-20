import logging
import os

from cryptography import x509 as cx509
from lxml import etree
from signxml import methods
from signxml.signer import XMLSigner
from signxml.verifier import XMLVerifier

logger = logging.getLogger("mock_watt.security")

DS_NS = "http://www.w3.org/2000/09/xmldsig#"
_IEC_MSG_NS = "http://iec.ch/TC57/2011/schema/message"
_INCLUSIVE_C14N = "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"


class SecurityEngine:
    """
    Handles W3C XML Digital Signatures and Canonicalization (C14N) 
    for IEC 62325-504 compliance.
    """
    
    def __init__(self, key_path: str, cert_path: str):
        """
        Initializes the cryptographic engine with local PKI materials.
        """
        self.key_path = key_path
        self.cert_path = cert_path
        
        self._validate_pki_materials()
        
        # Load the raw string data of the keys for signxml
        with open(self.key_path, "rb") as key_file:
            self.private_key = key_file.read()
            
        with open(self.cert_path, "rb") as cert_file:
            self.certificate = cert_file.read()

    def _validate_pki_materials(self):
        """Ensures the developer has actually generated the test certificates."""
        if not os.path.exists(self.key_path) or not os.path.exists(self.cert_path):
            raise FileNotFoundError(
                "PKI materials missing. Please run the generate_certs.sh script " + \
                "to create your local mock-watt.key and mock-watt.pem."
            )

    def sign_payload(self, xml_string: bytes) -> bytes:
        """
        Takes raw CIM XML, applies Exclusive C14N, and injects a W3C signature.
        
        :param xml_string: The raw, unsigned XML as bytes.
        :return: The digitally signed XML as bytes.
        """
        try:
            # Parse the raw XML into an lxml ElementTree
            root = etree.fromstring(xml_string)
            
            # IEC 62325 standards typically require SHA-256 and Exclusive C14N
            signer = XMLSigner(
                method=methods.enveloped,
                signature_algorithm="rsa-sha256",
                digest_algorithm="sha256",
                c14n_algorithm="http://www.w3.org/2001/10/xml-exc-c14n#"
            )
            
            # Sign the root element and inject the <ds:Signature> block
            signed_root = signer.sign(root, key=self.private_key, cert=self.certificate)
            
            # Return the signed XML string
            return etree.tostring(signed_root, pretty_print=False, encoding="utf-8")
            
        except Exception as e:
            raise RuntimeError(f"Failed to cryptographically sign the payload: {str(e)}")

    def sign_request_message(self, request_message_el: etree._Element) -> None:
        """
        Signs a RequestMessage element in-place per IEC 62325-504:
          - Inclusive C14N 1.0, RSA-SHA256, SHA-256 digest, enveloped signature
          - ds:Signature is injected by signxml then moved into mes:Header
          - ds:KeyInfo is enriched with X509IssuerSerial and X509SubjectName

        :param request_message_el: The mes:RequestMessage lxml element to sign (mutated).
        :raises RuntimeError: If signing fails.
        """
        try:
            signer = XMLSigner(
                method=methods.enveloped,
                signature_algorithm="rsa-sha256",
                digest_algorithm="sha256",
                c14n_algorithm=_INCLUSIVE_C14N,
            )
            signed_el = signer.sign(
                request_message_el, key=self.private_key, cert=self.certificate
            )

            # signxml appends ds:Signature as the last child of the signed element.
            # Per spec, it must live inside mes:Header.
            sig_el = signed_el.find(f"{{{DS_NS}}}Signature")
            if sig_el is not None:
                signed_el.remove(sig_el)
                mes_header = signed_el.find(f"{{{_IEC_MSG_NS}}}Header")
                if mes_header is not None:
                    mes_header.append(sig_el)

            self._enrich_key_info(signed_el)

            # Copy back into the caller's element reference so the mutation is visible
            request_message_el[:] = signed_el[:]
            request_message_el.attrib.update(signed_el.attrib)

        except Exception as e:
            raise RuntimeError(f"Failed to sign RequestMessage: {e}")

    def _enrich_key_info(self, signed_el: etree._Element) -> None:
        """Prepends X509IssuerSerial and X509SubjectName into ds:X509Data."""
        cert_obj = cx509.load_pem_x509_certificate(self.certificate)
        issuer_name = cert_obj.issuer.rfc4514_string()
        serial_number = str(cert_obj.serial_number)
        subject_name = cert_obj.subject.rfc4514_string()

        x509_data = signed_el.find(f".//{{{DS_NS}}}X509Data")
        if x509_data is None:
            return

        issuer_serial = etree.Element(f"{{{DS_NS}}}X509IssuerSerial")
        etree.SubElement(issuer_serial, f"{{{DS_NS}}}X509IssuerName").text = issuer_name
        etree.SubElement(issuer_serial, f"{{{DS_NS}}}X509SerialNumber").text = serial_number

        subj_el = etree.Element(f"{{{DS_NS}}}X509SubjectName")
        subj_el.text = subject_name

        x509_data.insert(0, issuer_serial)
        x509_data.insert(1, subj_el)

    def verify_payload(self, signed_xml_string: bytes) -> bytes:
        """
        Verifies the digital signature of an incoming XML document against
        the certificate that was loaded at construction time.

        :param signed_xml_string: The signed XML payload from the network.
        :return: The verified, raw XML content.
        :raises ValueError: If the signature is invalid.
        """
        root = etree.fromstring(signed_xml_string)
        verifier = XMLVerifier()
        try:
            verified_data = verifier.verify(root, x509_cert=self.certificate).signed_xml
            return etree.tostring(verified_data, encoding="utf-8")
        except Exception as e:
            raise ValueError(f"XML Signature Verification Failed: {str(e)}")

    @staticmethod
    def verify_inbound(signed_xml_bytes: bytes, ca_cert_path: str | None = None) -> bytes:
        """
        Verifies the digital signature of an inbound XML payload received by the server.

        Extracts the X.509 certificate embedded in ds:KeyInfo/ds:X509Certificate and
        verifies the signature against it. If ca_cert_path is provided, signxml also
        validates the embedded certificate against the CA trust chain.

        :param signed_xml_bytes: The signed XML payload as bytes.
        :param ca_cert_path: Optional path to the Root CA .pem for full chain validation.
        :return: The verified signed XML as bytes.
        :raises ValueError: If the payload is not valid XML, has no signature block,
                            has no embedded certificate, or the signature is invalid.
        """
        try:
            root = etree.fromstring(signed_xml_bytes)
        except etree.XMLSyntaxError as e:
            raise ValueError(f"Payload is not valid XML: {e}")

        # Ensure a Signature block is present before attempting verification.
        # The signature may be anywhere in the tree (e.g. inside mes:Header).
        if root.find(f".//{{{DS_NS}}}Signature") is None:
            raise ValueError(
                "No ds:Signature element found in payload — message is unsigned"
            )

        # Extract the certificate from ds:KeyInfo/ds:X509Certificate
        x509_el = root.find(f".//{{{DS_NS}}}X509Certificate")
        if x509_el is None or not (x509_el.text or "").strip():
            raise ValueError(
                "No X.509 certificate found in ds:KeyInfo — cannot verify signature"
            )

        # Wrap raw base64 DER in PEM headers so signxml accepts it as x509_cert
        cert_b64 = "".join(x509_el.text.split())
        cert_pem = (
            f"-----BEGIN CERTIFICATE-----\n{cert_b64}\n-----END CERTIFICATE-----\n"
        ).encode()

        cert_obj = cx509.load_pem_x509_certificate(cert_pem)
        logger.debug(
            "Verifying against embedded cert: subject=%s  issuer=%s  serial=%s",
            cert_obj.subject.rfc4514_string(),
            cert_obj.issuer.rfc4514_string(),
            cert_obj.serial_number,
        )

        sig_el = root.find(f".//{{{DS_NS}}}Signature")
        if sig_el is not None:
            c14n_el = sig_el.find(f"{{{DS_NS}}}SignedInfo/{{{DS_NS}}}CanonicalizationMethod")
            c14n_alg = c14n_el.get("Algorithm", "n/a") if c14n_el is not None else "n/a"
            ref_el = sig_el.find(f".//{{{DS_NS}}}Reference")
            ref_uri = ref_el.get("URI", "(empty)") if ref_el is not None else "n/a"
        else:
            c14n_alg = ref_uri = "n/a"
        logger.debug("Signature: c14n=%s  reference URI='%s'", c14n_alg, ref_uri)
        logger.debug("Verifying document (root tag: %s, %d bytes)", root.tag, len(signed_xml_bytes))

        verifier = XMLVerifier()
        try:
            if ca_cert_path:
                result = verifier.verify(root, x509_cert=cert_pem, ca_pem_file=ca_cert_path)
            else:
                # Verify signature math only — no chain validation
                result = verifier.verify(root, x509_cert=cert_pem)
            logger.debug("Signature verified OK (signed root: %s)", result.signed_xml.tag)
            return etree.tostring(result.signed_xml, encoding="utf-8")
        except Exception as e:
            logger.exception("<SecurityEngine -> caugh excpetion..")
            raise ValueError(f"XML Signature verification failed: {e}")