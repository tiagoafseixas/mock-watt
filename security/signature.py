import os

from lxml import etree
from signxml import methods
from signxml.signer import XMLSigner
from signxml.verifier import XMLVerifier


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

    def verify_payload(self, signed_xml_string: bytes) -> bytes:
        """
        Verifies the digital signature of an incoming XML document.
        (Crucial for Phase 2, but good to have ready now).
        
        :param signed_xml_string: The signed XML payload from the network.
        :return: The verified, raw XML content (Signature stripped or intact).
        :raises: signxml.exceptions.InvalidSignature if validation fails.
        """
        root = etree.fromstring(signed_xml_string)
        
        # We enforce X.509 certificate validation against the payload's signature
        verifier = XMLVerifier()
        
        try:
            # If this passes, the math checks out and the payload wasn't tampered with.
            verified_data = verifier.verify(root, x509_cert=self.certificate).signed_xml
            return etree.tostring(verified_data, encoding="utf-8")
        except Exception as e:
            raise ValueError(f"XML Signature Verification Failed: {str(e)}")