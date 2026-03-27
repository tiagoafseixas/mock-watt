import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request, Response
from lxml import etree

logger = logging.getLogger("mock_watt")

# signxml logs the full canonicalized XML at DEBUG level — suppress it
logging.getLogger("signxml").setLevel(logging.WARNING)

_INBOUND_DIR = os.path.join(os.getcwd(), "data", "inbound")

from security.signature import SecurityEngine
from server.schema_registry import SchemaRegistry
from transport.reply_builder import ReplyBuilder
from transport.soap_parser import SoapParser, SoapParseError

_SCHEMAS_DIR = os.path.join(os.getcwd(), "data", "active_schemas")

# Populated at startup via configure() — set by the CLI serve command
_registry: SchemaRegistry | None = None
_ca_cert_path: str | None = None


def configure(ca_cert_path: str | None = None) -> None:
    """
    Called by the CLI before uvicorn starts to inject runtime configuration.

    :param ca_cert_path: Optional path to Root CA .pem for XML-DSig chain validation.
    """
    global _registry, _ca_cert_path
    _registry = SchemaRegistry(_SCHEMAS_DIR)
    _ca_cert_path = ca_cert_path


@asynccontextmanager
async def _lifespan(app: FastAPI):
    global _registry
    if _registry is None:
        _registry = SchemaRegistry(_SCHEMAS_DIR)
    yield


app = FastAPI(title="Mock-Watt IEC 62325-504 Gateway", lifespan=_lifespan)


def _fault(code: str, reason: str, status: int = 400) -> Response:
    logger.warning("FAULT [%s] %s", code, reason)
    return Response(
        content=ReplyBuilder.build_soap_fault(code, reason),
        status_code=status,
        media_type="application/soap+xml; charset=utf-8",
    )


def _reply(
    noun: str,
    code: str,
    text: str,
    received_mrid: str = "",
    received_revision: str = "",
) -> Response:
    return Response(
        content=ReplyBuilder.build_reply_message(noun, code, text, received_mrid, received_revision),
        status_code=200,
        media_type="application/soap+xml; charset=utf-8",
    )


def _extract_field(element: etree._Element, tag: str) -> str:
    """
    Finds a direct child of element by local name and returns its 'v' attribute
    or text content. Tries the element's own namespace first, then no namespace.
    """
    ns = etree.QName(element.tag).namespace
    child = element.find(f"{{{ns}}}{tag}") if ns else element.find(tag)
    if child is None and ns:
        child = element.find(tag)
    if child is None:
        return ""
    return (child.get("v") or child.text or "").strip()


@app.post("/ws504")
async def ws504(request: Request) -> Response:
    logger.info(">ws504")
    # ------------------------------------------------------------------ #
    # Gate 1 — Transport & Security                                        #
    # ------------------------------------------------------------------ #

    # 1. Content-Type must be application/soap+xml
    content_type = request.headers.get("content-type", "")
    if "application/soap+xml" not in content_type:
        logger.info("<ws504 -> wrong content type, expected soap+xml...")
        return _fault(
            "soap:Sender",
            f"Invalid Content-Type '{content_type}'. "
            f"Expected: application/soap+xml; charset=utf-8",
        )

    # 2. Parse SOAP 1.2 envelope and extract IEC TC57 RequestMessage fields
    raw_body = await request.body()
    if not raw_body:
        logger.info("<ws504 -> body is empty")
        return _fault("soap:Sender", "Request body is empty")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")[:-3]
    os.makedirs(_INBOUND_DIR, exist_ok=True)
    inbound_path = os.path.join(_INBOUND_DIR, f"{timestamp}.xml")
    with open(inbound_path, "wb") as f:
        f.write(raw_body)
    logger.info("Saved inbound request to %s", inbound_path)

    try:
        parsed = SoapParser.parse_request(raw_body)
    except SoapParseError as exc:
        return _fault("soap:Sender", str(exc))

    # 3. Serialise the RequestMessage for signature verification
    try:
        request_message_bytes = etree.tostring(parsed.request_message, encoding="utf-8")
    except Exception as exc:
        return _fault("soap:Receiver", f"Failed to serialise RequestMessage: {exc}")

    # 4. Verify XML-DSig — ds:Signature lives in mes:Header and covers the full
    #    RequestMessage. If a CA cert is configured, the cert chain is also validated.
    try:
        SecurityEngine.verify_inbound(request_message_bytes, ca_cert_path=_ca_cert_path)
    except ValueError as exc:
        return _fault("soap:Sender", str(exc))

    # ------------------------------------------------------------------ #
    # Gate 2 — Business Payload                                            #
    # ------------------------------------------------------------------ #

    # 5. Resolve the root element name (strip namespace prefix)
    qname = etree.QName(parsed.payload_element)
    root_name = qname.localname
    logger.debug("Payload element: localname=%s  namespace=%s", root_name, qname.namespace)

    # 6. Dispatch and validate against the matching active XSD schema
    try:
        _registry.validate(root_name, parsed.payload_element)
    except KeyError as exc:
        return _reply(parsed.noun, "NOK", str(exc))
    except etree.DocumentInvalid as exc:
        return _reply(
            parsed.noun,
            "NOK",
            f"Schema validation failed for '{root_name}': {exc}",
        )

    # All gates passed — extract document identifiers and accept the message
    received_mrid = _extract_field(parsed.payload_element, "Identificador")
    received_revision = _extract_field(parsed.payload_element, "Versao")
    logger.debug("Accepting message: mrid=%r  revision=%r", received_mrid, received_revision)
    return _reply(parsed.noun, "OK", "", received_mrid, received_revision)
