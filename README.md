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

* **IEC 62325-504 Transport Simulation:** Natively acts as a standardized SOAP web service, exposing standard B2B endpoints (e.g., `PutMessage`).
* **Enterprise-Grade Cryptography:** Out-of-the-box verification of W3C XML Digital Signatures (XML-DSig) and Exclusive XML Canonicalization (C14N) using `signxml`.
* **Strict mTLS Enforcement:** Simulates a secure gateway requiring X.509 client certificate authentication.
* **Dynamic Business Payload Validation (IEC 62325-451 / CIM):** Payload-agnostic architecture. Upload any specific ENTSO-E or local market `.xsd` schema, and Mock-Watt will instantly validate the inner XML payload, catching malformed UUIDs or incorrect ISO 8601 timestamps in milliseconds.
* **Zero-Database Footprint:** Runs entirely locally using SQLite and SQLAlchemy for state management. No Dockerized databases required.

## 🚀 How to Use Mock-Watt

### 1. Prerequisites
* Python 3.9+
* OpenSSL (for generating local testing certificates)

### 2. Installation
Clone the repository and install the required dependencies:
```bash
git clone [https://github.com/tiagoafseixas/mock-watt.git](https://github.com/tiagoafseixas/mock-watt.git)
cd mock-watt
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

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
Start the Mock-Watt Uvicorn server, which will launch the mTLS-secured SOAP endpoint:
```bash
python mock_watt/main.py
```
*The server is now listening on `https://localhost:8443` and ready to receive your platform's signed SOAP messages.*

## 🏗️ The Technology Stack
* **Routing:** FastAPI + Uvicorn
* **SOAP/WSDL:** Spyne & Zeep
* **XML Validation:** lxml
* **Cryptography:** signxml
