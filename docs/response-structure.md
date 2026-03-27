# IEC 62325-504 Response Structure

## Overview

When mock-watt accepts a `RequestMessage`, it replies with a SOAP 1.2 `ResponseMessage`
that mirrors the structure produced by the TSO. The response is a `mes:ResponseMessage`
wrapped in a `soap:Body`, containing a message header, a reply status block, and a
business acknowledgement payload.

---

## Full Response Structure

```xml
<tns:Envelope xmlns:tns="http://www.w3.org/2003/05/soap-envelope">
    <tns:Body>
        <ns:ResponseMessage xmlns:ns="http://iec.ch/TC57/2011/schema/message">
            <ns:Header>
                <ns:Verb>reply</ns:Verb>
                <ns:Noun>Acknowledgement_MarketDocument</ns:Noun>
                <ns:Context>PRODUCTION</ns:Context>
                <ns:Timestamp>2026-03-23T08:00:07.616Z</ns:Timestamp>
                <Signature xmlns="http://www.w3.org/2000/09/xmldsig#">
                    <!-- XML-DSig enveloped signature covering ResponseMessage -->
                </Signature>
            </ns:Header>
            <ns:Reply>
                <ns:Result>OK</ns:Result>
            </ns:Reply>
            <ns:Payload>
                <ack:Acknowledgement_MarketDocument
                    xmlns:ack="urn:iec62325.351:tc57wg16:451-1:acknowledgementdocument:8:0">
                    <ack:mRID>ACK_messagePRRXXXX_20260323.3</ack:mRID>
                    <ack:createdDateTime>2026-03-23T08:00:07Z</ack:createdDateTime>
                    <ack:sender_MarketParticipant.mRID codingScheme="A01">10XXX-XXX----4-A</ack:sender_MarketParticipant.mRID>
                    <ack:sender_MarketParticipant.marketRole.type>A04</ack:sender_MarketParticipant.marketRole.type>
                    <ack:receiver_MarketParticipant.mRID codingScheme="A01"/>
                    <ack:receiver_MarketParticipant.marketRole.type>A11</ack:receiver_MarketParticipant.marketRole.type>
                    <ack:received_MarketDocument.mRID>received_document_mrID_</ack:received_MarketDocument.mRID>
                    <ack:received_MarketDocument.revisionNumber>3</ack:received_MarketDocument.revisionNumber>
                    <ack:Reason>
                        <ack:code>A01</ack:code>
                        <ack:text>Message fully accepted</ack:text>
                    </ack:Reason>
                </ack:Acknowledgement_MarketDocument>
            </ns:Payload>
        </ns:ResponseMessage>
    </tns:Body>
</tns:Envelope>
```

---

## Header Fields

| Field | Value | Notes |
|---|---|---|
| `ns:Verb` | `reply` | Always `reply` for responses |
| `ns:Noun` | `Acknowledgement_MarketDocument` | Fixed — not an echo of the request Noun |
| `ns:Context` | `PRODUCTION` | Fixed |
| `ns:Timestamp` | ISO 8601 UTC with milliseconds | Generated at response time |
| `Signature` | XML-DSig enveloped signature | Signs the entire `ResponseMessage`; currently not implemented in mock-watt — see Pending section below |

---

## Reply Block

The `ns:Reply` block conveys the processing outcome.

| Field | OK value | NOK value |
|---|---|---|
| `ns:Result` | `OK` | `NOK` |
| `ns:Text` | *(absent)* | Human-readable error description |

`ns:Text` is only included when `ns:Result` is `NOK`. The TSO does not include `ns:Text`
in successful responses.

---

## Payload — Acknowledgement_MarketDocument

The `ns:Payload` block is only present on **OK** responses. It contains a single
`ack:Acknowledgement_MarketDocument` conforming to the IEC 62325-451-1 schema
(namespace `urn:iec62325.351:tc57wg16:451-1:acknowledgementdocument:8:0`).

### Fields

| Field | Source | Notes |
|---|---|---|
| `ack:mRID` | `ACK_` + original document mRID | Unique identifier for this acknowledgement |
| `ack:createdDateTime` | `datetime.now(UTC)` | Formatted as `YYYY-MM-DDTHH:MM:SSZ` (no sub-seconds) |
| `ack:sender_MarketParticipant.mRID` | Hardcoded placeholder | EIC of the TSO (mock: `10XPT-REN----0-V`) |
| `ack:sender_MarketParticipant.marketRole.type` | `A04` | TSO role code (ENTSO-E codification) |
| `ack:receiver_MarketParticipant.mRID` | Empty | Sender's EIC — not yet extracted from request |
| `ack:receiver_MarketParticipant.marketRole.type` | `A11` | Market participant role code |
| `ack:received_MarketDocument.mRID` | Extracted from request payload | Original document identifier |
| `ack:received_MarketDocument.revisionNumber` | Extracted from request payload | Original document revision |
| `ack:Reason/code` | `A01` | ENTSO-E acknowledgement reason code: fully accepted |
| `ack:Reason/text` | `Message fully accepted` | Human-readable reason |

### Extraction of `mRID` and `revisionNumber`

The `received_MarketDocument.mRID` and `received_MarketDocument.revisionNumber` are
extracted in `server/app.py` from `parsed.payload_element` after signature and schema
validation pass. The expected element names inside the business document are
`Identificador` and `Versao` (namespace-qualified, matching the payload's own namespace).
If either element is absent, the field is left empty in the acknowledgement.

---

## NOK Response (Schema or Routing Failure)

When Gate 2 fails (unknown schema or schema validation error), the response does **not**
include a `ns:Payload`. Only `ns:Result` and `ns:Text` are returned:

```xml
<ns:Reply>
    <ns:Result>NOK</ns:Result>
    <ns:Text>Schema validation failed for 'MensagemOferBandaFRR': ...</ns:Text>
</ns:Reply>
```

SOAP transport faults (Gate 1 failures) follow a different structure — see
[security.md](security.md) for the SOAP fault envelope format.

---

## Pending

### Response Signing

The TSO signs its `ResponseMessage` with the same XML-DSig / RSA-SHA256 / Inclusive C14N
scheme used for inbound requests. Mock-watt does not currently sign responses. Adding
response signing requires wiring `SecurityEngine.sign_request_message()` (or an equivalent
`sign_response_message()`) into the response path before the envelope is serialised.

This is tracked as a future improvement — the client must be configured to skip or tolerate
unsigned mock responses in the interim.
