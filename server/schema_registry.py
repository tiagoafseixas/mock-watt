import logging
import os

from lxml import etree

logger = logging.getLogger("mock_watt.registry")

XS_NS = "http://www.w3.org/2001/XMLSchema"


class SchemaRegistry:
    """
    Scans a directory tree for XSD files and registers them by root element name.

    Each XSD's top-level xs:element declarations are indexed so that incoming
    payloads can be dispatched and validated by their root element name alone.
    """

    def __init__(self, schemas_dir: str):
        self._schemas: dict[str, etree.XMLSchema] = {}
        self._load_all(schemas_dir)

    @property
    def known_elements(self) -> list[str]:
        return sorted(self._schemas.keys())

    def _load_all(self, schemas_dir: str) -> None:
        if not os.path.isdir(schemas_dir):
            logger.warning("Schemas directory not found: %s", schemas_dir)
            return
        for dirpath, _, filenames in os.walk(schemas_dir):
            for filename in filenames:
                if filename.endswith((".xsd", ".xml")):
                    self._try_load(os.path.join(dirpath, filename))
        logger.info("Schema registry loaded: %s", self.known_elements)

    def _try_load(self, path: str) -> None:
        try:
            doc = etree.parse(path)
            schema_root = doc.getroot()

            # Only process files whose root is xs:schema
            if schema_root.tag != f"{{{XS_NS}}}schema":
                return

            schema = etree.XMLSchema(doc)

            # Register every top-level xs:element declaration as an entry point
            for el in schema_root.iterchildren(f"{{{XS_NS}}}element"):
                name = el.get("name")
                if name:
                    self._schemas[name] = schema
        except Exception as exc:
            logger.warning("Failed to load schema %s: %s", path, exc)

    def validate(self, root_element_name: str, xml_element: etree._Element) -> None:
        """
        Validates xml_element against the schema registered for root_element_name.

        :raises KeyError: If no schema is registered for the given root element name.
        :raises etree.DocumentInvalid: If the element fails schema validation.
        """
        if root_element_name not in self._schemas:
            raise KeyError(
                f"No active schema found for root element '{root_element_name}'. "
                f"Place the relevant .xsd file in data/active_schemas/. "
                f"Currently registered: {self.known_elements}"
            )
        self._schemas[root_element_name].assertValid(xml_element)
