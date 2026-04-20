# IEC 62325-504 Security Architecture

## Overview

Mock-Watt implements the security model mandated by the IEC 62325-504 standard for B2B
energy market communications. Every outbound message is digitally signed using W3C XML
Digital Signatures (XML-DSig), and every inbound message is verified before its business
payload is processed. Transport-level confidentiality and mutual authentication are enforced
via mutual TLS (mTLS).

---

## Standards Employed

| Layer | Standard |
|---|---|
| Transport security | TLS 1.2+ with mutual client certificate authentication (mTLS) |
| Message integrity | W3C XML-DSig 1.0 (enveloped signature) |
| Signature algorithm | RSA-SHA256 (`rsa-sha256`) |
| Digest algorithm | SHA-256 (`sha256`) |
| Canonicalization | Inclusive C14N 1.0 (`http://www.w3.org/TR/2001/REC-xml-c14n-20010315`) |
| Certificate format | X.509 v3 (PEM) |

---

## Message Structure

All messages conform to the SOAP 1.2 + IEC TC57 framing defined by IEC 62325-504:

```xml
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
    <soap:Body>
        <RequestMessage xmlns="http://iec.ch/TC57/2011/schema/message">
            <Header>
                <Verb>create</Verb>
                <Noun>MensagemOferArranquePRR</Noun>
                <Timestamp>2026-03-23T08:00:06.935Z</Timestamp>
                <Signature xmlns="http://www.w3.org/2000/09/xmldsig#">
                    <!-- XML-DSig enveloped signature covering RequestMessage -->
                </Signature>
            </Header>
            <Request/>
            <Payload>
                <!-- Business document (CIM XML) -->
            </Payload>
        </RequestMessage>
    </soap:Body>
</soap:Envelope>
```

Key structural points:

- `soap:Envelope` / `soap:Body` — SOAP 1.2 framing (namespace `http://www.w3.org/2003/05/soap-envelope`)
- `RequestMessage` — IEC TC57 message wrapper (namespace `http://iec.ch/TC57/2011/schema/message`)
- `Header` — contains routing metadata (Verb, Noun, Timestamp) and the digital signature
- `Request` — empty element required by the standard
- `Payload` — contains the business document (CIM XML), e.g. `MensagemOferBandaFRR`

---

## XML Digital Signature

### Signature Placement

The `ds:Signature` element is placed **inside `mes:Header`**, as a sibling of `Verb`, `Noun`,
and `Timestamp`. It is an *enveloped* signature: the signed content (`RequestMessage`)
contains the signature element itself.

This means the signature covers the entire `RequestMessage`, including all Header fields
and the business `Payload`. Any tampering with the Verb, Noun, Timestamp, or business
document will invalidate the signature.

### What Is Signed

The `ds:Reference URI=""` convention means the root of the signed document — which is
`RequestMessage`. The `enveloped-signature` transform strips the `ds:Signature` element
from the tree before computing the digest, so the signature does not cover itself.

Digest computation:

1. Start with the `RequestMessage` element tree
2. Apply `enveloped-signature` transform: remove `ds:Signature` from `Header`
3. Apply Inclusive C14N 1.0 to the resulting tree
4. Compute SHA-256 digest — this becomes `ds:DigestValue`

Signature computation:

1. Serialize `ds:SignedInfo` using Inclusive C14N 1.0
2. Sign with RSA-SHA256 using the sender's private key — this becomes `ds:SignatureValue`

### Algorithms

```xml
<SignedInfo>
    <CanonicalizationMethod
        Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"/>
    <SignatureMethod
        Algorithm="http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"/>
    <Reference URI="">
        <Transforms>
            <Transform
                Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature"/>
        </Transforms>
        <DigestMethod Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>
        <DigestValue>...</DigestValue>
    </Reference>
</SignedInfo>
```

Note that only the `enveloped-signature` transform is applied on the Reference — no
additional C14N transform is listed. Inclusive C14N is applied implicitly as the
default canonicalization for the digest computation.

### KeyInfo Structure

`ds:KeyInfo` carries three pieces of certificate information to allow the receiver to
identify and validate the signer's certificate without requiring out-of-band lookup:

```xml
<KeyInfo>
    <X509Data>
        <X509IssuerSerial>
            <X509IssuerName>CN=RA-ADCS-2-CA, DC=ren, DC=pt</X509IssuerName>
            <X509SerialNumber>113733819399...</X509SerialNumber>
        </X509IssuerSerial>
        <X509SubjectName>CN=Certificado-Qua G2, OU=..., O=..., L=Lisboa, C=PT</X509SubjectName>
        <X509Certificate>MIIFf...</X509Certificate>
    </X509Data>
</KeyInfo>
```

| Element | Purpose |
|---|---|
| `X509IssuerSerial` | Identifies the issuing CA and certificate serial number |
| `X509SubjectName` | Human-readable subject distinguished name |
| `X509Certificate` | Full DER-encoded certificate in Base64 — used for signature verification |

The receiver extracts `X509Certificate` and uses it directly to verify the signature.
If a CA certificate is configured, the certificate chain is also validated.

---

## Outbound Flow (Signing)

The following steps are executed by `cli.py` → `execute_request()` when sending a message:

```
1. Load raw business XML from file
2. Detect or accept the IEC TC57 Noun from the root element name
3. Build an unsigned RequestMessage element:
       SoapBuilder.build_request_message(verb, noun, raw_xml)
       → RequestMessage with Header (Verb/Noun/Timestamp), Request, Payload
4. Sign the RequestMessage:
       SecurityEngine.sign_request_message(request_message_element)
       → signxml signs RequestMessage (injects ds:Signature at end)
       → ds:Signature is moved from RequestMessage tail into mes:Header
       → KeyInfo is enriched with X509IssuerSerial and X509SubjectName
5. Wrap in SOAP envelope:
       SoapBuilder.wrap_in_envelope(request_message_element)
       → soap:Envelope / soap:Body / RequestMessage
6. POST via mTLS to the target HTTPS endpoint
```

### Code Components

| Component | Responsibility |
|---|---|
| `SecurityEngine.sign_request_message()` | Signs the `RequestMessage` element, moves `ds:Signature` to `Header`, enriches `KeyInfo` |
| `SoapBuilder.build_request_message()` | Builds the unsigned `RequestMessage` lxml element |
| `SoapBuilder.wrap_in_envelope()` | Wraps a `RequestMessage` element in a SOAP 1.2 envelope |

---

## Inbound Verification Flow

The following gates are applied by `server/app.py` → `POST /ws504`:

```
Gate 1 — Transport & Security
  1. Content-Type must be application/soap+xml
  2. Body must be non-empty, well-formed XML
  3. SOAP 1.2 structure: Envelope → Body → RequestMessage
  4. mes:Header must have non-empty Verb, Noun, Timestamp
  5. mes:Payload must have exactly one child element
  6. Serialize the RequestMessage element
  7. Locate ds:Signature in mes:Header; extract X509Certificate from ds:KeyInfo
  8. Verify XML-DSig: check DigestValue and SignatureValue
     - If ca_cert_path is configured: also validate certificate chain

Gate 2 — Business Payload
  9.  Resolve root element name of the business document (strip namespace prefix)
  10. Dispatch to the matching active XSD schema (data/active_schemas/)
  11. assertValid() — reject with NOK ReplyMessage if schema fails
  12. Accept with OK ReplyMessage
```

### Code Components

| Component | Responsibility |
|---|---|
| `SoapParser.parse_request()` | Parses and structurally validates the SOAP envelope; returns `ParsedRequest` including the live `request_message` element |
| `SecurityEngine.verify_inbound()` | Verifies `ds:Signature` within the `RequestMessage`; extracts embedded cert for verification; optionally validates CA chain |
| `SchemaRegistry` | Loads XSD schemas from `data/active_schemas/`; dispatches by root element name |

---

## Key Management

### Generating Local Test Certificates

```bash
scripts/generate_certs.sh
```

This produces three files in `data/certs/`:

| File | Purpose |
|---|---|
| `rootCA.key` | Root CA private key (never leaves the machine) |
| `rootCA.pem` | Root CA certificate — passed as `--ca` to the server |
| `mock-watt.key` | Gateway private key — passed as `--key` to both CLI commands |
| `mock-watt.pem` | Gateway certificate signed by rootCA — passed as `--cert` |

### mTLS Configuration

When the server is started with `--ca`, Uvicorn enforces `ssl.CERT_REQUIRED`. Every
client must present a certificate signed by the configured CA during the TLS handshake.
Without `--ca`, the server accepts any TLS connection (signature verification still applies
at the application layer).

---

## Addenda: Implementation Findings

The following discrepancies were identified by comparing the initial Mock-Watt
implementation against the reference example.

### Finding 1 — Signature Location (Critical)

**Initial implementation:** `ds:Signature` was embedded inside the business document
element, signing only the business payload.

**Reference example:** `ds:Signature` is inside `mes:Header`, signing the entire
`RequestMessage` (including Header fields Verb, Noun, Timestamp, and the Payload).

**Impact:** The entire `RequestMessage` must be treated as the signed unit. Tampered
routing metadata (Verb/Noun) is now detectable, not just tampered payload content.

**Resolution:** `SecurityEngine.sign_request_message()` signs the `RequestMessage`
element and moves the signature into `mes:Header`. `SecurityEngine.verify_inbound()`
receives `RequestMessage` bytes and locates `ds:Signature` anywhere in the subtree.

---

### Finding 2 — Canonicalization Algorithm

**Initial implementation:** Exclusive C14N (`http://www.w3.org/2001/10/xml-exc-c14n#`)
was used for both `CanonicalizationMethod` and as an additional Reference transform.

**Reference example:** Inclusive C14N 1.0 (`http://www.w3.org/TR/2001/REC-xml-c14n-20010315`).

**Impact:** The DigestValue computed with Exclusive C14N will not match the one computed
with Inclusive C14N. The two algorithms differ in how they handle namespace declarations
from ancestor elements.

**Resolution:** `XMLSigner` is now configured with
`c14n_algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"`.

---

### Finding 3 — Reference Transforms

**Initial implementation:** Two transforms were listed on the `ds:Reference`:
`enveloped-signature` followed by the Exclusive C14N transform.

**Reference example:** Only `enveloped-signature` is listed. Inclusive C14N is applied
implicitly as the default — no explicit C14N transform on the Reference.

**Impact:** An extra transform entry does not necessarily break verification, but it
diverges from the operator's expected format and may be rejected by strict parsers.

**Resolution:** Follows automatically from switching to Inclusive C14N — `signxml`
does not add an explicit C14N transform on the Reference when using Inclusive C14N.

---

### Finding 4 — KeyInfo Content

**Initial implementation:** `ds:KeyInfo` contained only `ds:X509Data/ds:X509Certificate`.

**Reference example:** `ds:KeyInfo/ds:X509Data` contains all three:
`X509IssuerSerial`, `X509SubjectName`, and `X509Certificate`.

**Impact:** Receiving systems that use `X509IssuerSerial` to look up the certificate
from a local store (rather than trusting the embedded cert directly) will fail.

**Resolution:** After `signxml` injects the signature, `SecurityEngine._enrich_key_info()`
appends `X509IssuerSerial` and `X509SubjectName` to `ds:X509Data`. The existing
`X509Certificate` element is preserved. Inbound verification continues to use
`X509Certificate` for signature verification.
