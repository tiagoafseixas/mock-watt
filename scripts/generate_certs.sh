#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "⚡ Mock-Watt PKI Generator"
echo "--------------------------------------------------"

# Determine the absolute path to the data/certs directory
# This ensures the script works whether run from the root or the scripts/ folder
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
CERT_DIR="$(dirname "$SCRIPT_DIR")/data/certs"

# Create the directory if it doesn't exist
mkdir -p "$CERT_DIR"
echo "📁 Target directory: $CERT_DIR"

# ---------------------------------------------------------
# 1. Generate the Local Root Certificate Authority (CA)
# ---------------------------------------------------------
echo "🔐 1. Generating Local Root CA (rootCA.key, rootCA.pem)..."
openssl genrsa -out "$CERT_DIR/rootCA.key" 4096 2>/dev/null
openssl req -x509 -new -nodes -key "$CERT_DIR/rootCA.key" -sha256 -days 3650 \
    -out "$CERT_DIR/rootCA.pem" \
    -subj "/C=PT/ST=Lisboa/L=Lisboa/O=Mock-Watt Local CA/CN=Mock-Watt Root" 2>/dev/null

# ---------------------------------------------------------
# 2. Generate the Mock-Watt Client/Server Certificate
# ---------------------------------------------------------
echo "🔑 2. Generating Mock-Watt Certificate (mock-watt.key, mock-watt.csr)..."
openssl genrsa -out "$CERT_DIR/mock-watt.key" 2048 2>/dev/null
openssl req -new -key "$CERT_DIR/mock-watt.key" \
    -out "$CERT_DIR/mock-watt.csr" \
    -subj "/C=PT/ST=Lisboa/L=Lisboa/O=Mock-Watt Gateway/CN=mock-watt.local" 2>/dev/null

# ---------------------------------------------------------
# 3. Sign the Mock-Watt Certificate with the Root CA
# ---------------------------------------------------------
echo "✍️  3. Signing Mock-Watt Certificate with Root CA..."
openssl x509 -req -in "$CERT_DIR/mock-watt.csr" \
    -CA "$CERT_DIR/rootCA.pem" \
    -CAkey "$CERT_DIR/rootCA.key" \
    -CAcreateserial \
    -out "$CERT_DIR/mock-watt.pem" \
    -days 365 -sha256 2>/dev/null

# ---------------------------------------------------------
# 4. Cleanup temporary files
# ---------------------------------------------------------
echo "🧹 4. Cleaning up certificate signing requests..."
rm -f "$CERT_DIR/mock-watt.csr"
rm -f "$CERT_DIR/rootCA.srl"

echo "--------------------------------------------------"
echo "✅ PKI Generation Complete!"
echo ""
echo "Files created in data/certs/:"
echo "  - rootCA.pem      (Add this to your platform's Trust Store for mTLS)"
echo "  - rootCA.key      (Keep secret, used to sign other test certs)"
echo "  - mock-watt.pem   (The Mock-Watt public certificate)"
echo "  - mock-watt.key   (The Mock-Watt private key used for XML-DSig)"
echo "--------------------------------------------------"