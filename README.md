<div align="center">
  <h1>⚡ Mock-Watt</h1>
  <p><strong>The Agnostic, Local Simulator for European Energy Market Communications (IEC 62325)</strong></p>
</div>

## 📖 What is Mock-Watt?

Integrating with European Transmission System Operators (TSOs) requires strict adherence to the ENTSO-E Electronic Data Interchange (EDI) standards. Mock-Watt is a lightweight, open-source Python server that mocks a standard European TSO B2B gateway directly on your `localhost`. 

It allows energy market participants, aggregators, and software vendors to rigorously test their outbound messages—validating SOAP transport, mutual TLS (mTLS), W3C XML Digital Signatures, and CIM XML formatting—without needing access to slow, restricted, or complex external TSO homologation testbeds.

## 🎯 The Intent: Decoupled by Design

Historically, testing these integrations meant fighting with cryptography and business logic simultaneously against a black-box server. We built Mock-Watt on a crucial architectural reality of the European grid: **the transport layer does not care about the business logic.** Mock-Watt decouples the pipeline from the payload:
1. **The Transport & Security Gate:** It strictly enforces network security (mTLS) and cryptographic math (Canonicalization and XML-DSig). If a signature is invalid, the message is dropped at the gate.
2. **The Payload Gate:** It is entirely agnostic to the business process. You provide the `.xsd` schema. If the message passes the security gate, Mock-Watt validates the inner XML against your provided schema.

## ✨ Current Features

* **IEC 62325-504 Transport Simulation:** Natively acts as a standardized SOAP 1.2 web service, building IEC TC57 `RequestMessage` envelopes with Verb, Noun, and Timestamp headers.
* **Enterprise-Grade Cryptography:** Out-of-the-box verification of W3C XML Digital Signatures (XML-DSig) and Exclusive XML Canonicalization (C14N) using `signxml`.
* **Strict mTLS Enforcement:** Simulates a secure gateway requiring X.509 client certificate authentication.
* **Dynamic Business Payload Validation (IEC 62325-451 / CIM):** Payload-agnostic architecture. Upload any specific ENTSO-E or local market `.xsd` schema, and Mock-Watt will instantly validate the inner XML payload, catching malformed UUIDs or incorrect ISO 8601 timestamps in milliseconds.
* **Zero-Database Footprint:** Runs entirely locally using SQLite and SQLAlchemy for state management. No Dockerized databases required.

## 🚀 How to Use Mock-Watt

### 1. Prerequisites
* Python 3.9+
* OpenSSL (for generating local testing certificates)

### 2. Installation
Clone the repository, then install Mock-Watt itself (editable mode) rather than just its dependencies. This registers the `mock-watt` command on your `PATH`, which is required by the scripts in `scripts/` and the CLI reference below:
```bash
git clone [https://github.com/tiagoafseixas/mock-watt.git](https://github.com/tiagoafseixas/mock-watt.git)
cd mock-watt
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e .
```
*`pip install -e .` reads `setup.py`, installs the dependencies declared there, and creates the `mock-watt` console script. Skipping this step and only running `pip install -r requirements.txt` will leave the `mock-watt` command unavailable.*

### 3. Generate Local Test Certificates (PKI)
Because Mock-Watt enforces strict mutual TLS (mTLS) and XML signing, you need local dummy certificates. We have provided a script to generate a local Root CA and the necessary client/server keys.

```bash
cd scripts/
chmod +x generate_certs.sh
./generate_certs.sh
```
*(This will output your `rootCA.pem` and your local `mock-watt.pem`/`mock-watt.key` into the `data/certs/` directory).*

### 4. Upload Your Target Schema
Place the `.xsd` file for the specific energy market process you want to test (e.g., balancing, scheduling, acknowledgements) into the `data/active_schemas/` directory. Mock-Watt will automatically load this to validate incoming XML payloads.

### 5. Run the Server
Start the Mock-Watt Uvicorn server, which will launch the mTLS-secured SOAP endpoint, using the provided `scripts/serve.sh` wrapper:
```bash
bash scripts/serve.sh
```
*This wraps `mock-watt serve --cert data/certs/mock-watt.pem --key data/certs/mock-watt.key --ca data/certs/rootCA.pem --port 8444`. It is a shell script, not a Python one — run it with `bash`/`sh`, or `chmod +x` it and run `./scripts/serve.sh`. Running `python scripts/serve.sh` will fail with a `SyntaxError`. It also requires `mock-watt` to be installed (step 2) and points at the certificates generated in step 3 — adjust the paths/port in the script if yours differ.*

*The server is now listening on `https://localhost:8444` and ready to receive your platform's signed SOAP messages.*

---

## 🖥️ CLI Reference — `mock-watt send`

The `send` command signs a CIM XML payload, wraps it in a SOAP 1.2 + IEC TC57 `RequestMessage` envelope, and transmits it via mTLS.

```bash
mock-watt send [OPTIONS]
```

### Required arguments

| Argument | Description |
|---|---|
| `--payload PATH` | Path to the raw CIM XML document to send |
| `--url URL` | Target HTTPS endpoint |
| `--cert PATH` | Client certificate for mTLS (`.pem`) |
| `--key PATH` | Private key for mTLS (`.key`) |

### Optional arguments

| Argument | Default | Description |
|---|---|---|
| `--ca PATH` | — | Root CA certificate for server verification. If omitted, server certificate verification is skipped |
| `--verb VERB` | `created` | IEC TC57 `mes:Verb` placed in the SOAP `RequestMessage` header |
| `--noun NOUN` | *(auto-detected)* | IEC TC57 `mes:Noun` placed in the SOAP `RequestMessage` header. Defaults to the root element name of the payload (e.g. `MensagemOferBandaFRR`) |
| `--store-request` | off | Save the outbound SOAP envelope to `data/outbound/<name>_<timestamp>.xml` |
| `--store-response` | off | Save the raw server response to `data/inbound/<name>_<timestamp>_response.xml` |

### SOAP envelope structure

Each `send` invocation produces a SOAP 1.2 envelope following the IEC TC57 `RequestMessage` framing:

```xml
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
               xmlns:mes="http://iec.ch/TC57/2011/schema/message">
  <soap:Header/>
  <soap:Body>
    <mes:RequestMessage>
      <mes:Header>
        <mes:Verb>created</mes:Verb>
        <mes:Noun>MensagemOferBandaFRR</mes:Noun>
        <mes:Timestamp>2026-03-23T11:04:09Z</mes:Timestamp>
      </mes:Header>
      <mes:Payload>
        <!-- signed CIM XML document -->
      </mes:Payload>
    </mes:RequestMessage>
  </soap:Body>
</soap:Envelope>
```

### Examples

Minimal — noun auto-detected from the payload root element:
```bash
mock-watt send \
  --payload data/MensagemOferBandaFRR.xml \
  --url https://localhost:8443/ws504 \
  --cert data/certs/mock-watt.pem \
  --key data/certs/mock-watt.key
```

Full — all options explicit, store both request and response:
```bash
mock-watt send \
  --payload data/MensagemOferBandaFRR.xml \
  --url https://localhost:8443/ws504 \
  --cert data/certs/mock-watt.pem \
  --key data/certs/mock-watt.key \
  --ca data/certs/rootCA.pem \
  --verb created \
  --noun MensagemOferBandaFRR \
  --store-request \
  --store-response
```

## 🖥️ CLI Reference — `mock-watt serve`

The `serve` command starts the Mock-Watt gateway: an mTLS-secured SOAP endpoint that verifies inbound XML signatures and validates payloads against your uploaded `.xsd` schemas.

```bash
mock-watt serve [OPTIONS]
```

### Required arguments

| Argument | Description |
|---|---|
| `--cert PATH` | Server certificate for mTLS (`.pem`) |
| `--key PATH` | Server private key (`.key`) |

### Optional arguments

| Argument | Default | Description |
|---|---|---|
| `--ca PATH` | — | Root CA certificate for verifying client certificates |
| `--host HOST` | `0.0.0.0` | Bind host |
| `--port PORT` | `8443` | Bind port |

### Example

```bash
mock-watt serve \
  --cert data/certs/mock-watt.pem \
  --key data/certs/mock-watt.key \
  --ca data/certs/rootCA.pem \
  --port 8444
```

*This is exactly what `scripts/serve.sh` runs — see [Run the Server](#5-run-the-server) above.*

## 🏗️ The Technology Stack
* **Routing:** FastAPI + Uvicorn
* **SOAP/WSDL:** Spyne & Zeep
* **XML Validation:** lxml
* **Cryptography:** signxml
