import pytest
from lxml import etree

from server.schema_registry import SchemaRegistry

# Minimal XSD that declares a top-level <Document> element
_DOCUMENT_XSD = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:element name="Document">
    <xs:complexType>
      <xs:sequence>
        <xs:element name="ID" type="xs:string"/>
      </xs:sequence>
    </xs:complexType>
  </xs:element>
</xs:schema>
"""

# Valid and invalid XML for that schema
_VALID_DOCUMENT = b"<Document><ID>DOC-001</ID></Document>"
_INVALID_DOCUMENT = b"<Document><WrongField>oops</WrongField></Document>"

# A file that is not an XSD (no xs:schema root)
_NOT_AN_XSD = b"<root><element>not a schema</element></root>"


@pytest.fixture
def schema_dir(tmp_path):
    """A temp directory with a single valid XSD."""
    (tmp_path / "document.xsd").write_bytes(_DOCUMENT_XSD)
    return tmp_path


@pytest.fixture
def registry(schema_dir):
    return SchemaRegistry(str(schema_dir))


class TestSchemaRegistryLoading:
    def test_loads_from_valid_directory(self, schema_dir):
        reg = SchemaRegistry(str(schema_dir))
        assert "Document" in reg.known_elements

    def test_empty_directory_has_no_schemas(self, tmp_path):
        reg = SchemaRegistry(str(tmp_path))
        assert reg.known_elements == []

    def test_nonexistent_directory_has_no_schemas(self, tmp_path):
        reg = SchemaRegistry(str(tmp_path / "does_not_exist"))
        assert reg.known_elements == []

    def test_non_xsd_xml_file_is_skipped(self, tmp_path):
        (tmp_path / "not_a_schema.xml").write_bytes(_NOT_AN_XSD)
        reg = SchemaRegistry(str(tmp_path))
        assert reg.known_elements == []

    def test_malformed_xsd_is_skipped(self, tmp_path):
        (tmp_path / "broken.xsd").write_bytes(b"not xml at all <<<")
        reg = SchemaRegistry(str(tmp_path))
        assert reg.known_elements == []

    def test_scans_subdirectories(self, tmp_path):
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "document.xsd").write_bytes(_DOCUMENT_XSD)
        reg = SchemaRegistry(str(tmp_path))
        assert "Document" in reg.known_elements

    def test_multiple_xsd_files_all_registered(self, tmp_path):
        (tmp_path / "doc.xsd").write_bytes(_DOCUMENT_XSD)
        other_xsd = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:element name="Report">
    <xs:complexType>
      <xs:sequence>
        <xs:element name="Title" type="xs:string"/>
      </xs:sequence>
    </xs:complexType>
  </xs:element>
</xs:schema>
"""
        (tmp_path / "report.xsd").write_bytes(other_xsd)
        reg = SchemaRegistry(str(tmp_path))
        assert "Document" in reg.known_elements
        assert "Report" in reg.known_elements

    def test_xsd_with_xml_extension_is_loaded(self, tmp_path):
        (tmp_path / "document.xml").write_bytes(_DOCUMENT_XSD)
        reg = SchemaRegistry(str(tmp_path))
        assert "Document" in reg.known_elements


class TestSchemaRegistryValidate:
    def test_valid_element_passes(self, registry):
        el = etree.fromstring(_VALID_DOCUMENT)
        registry.validate("Document", el)  # should not raise

    def test_invalid_element_raises_document_invalid(self, registry):
        el = etree.fromstring(_INVALID_DOCUMENT)
        with pytest.raises(etree.DocumentInvalid):
            registry.validate("Document", el)

    def test_unknown_root_element_raises_key_error(self, registry):
        el = etree.fromstring(_VALID_DOCUMENT)
        with pytest.raises(KeyError, match="UnknownElement"):
            registry.validate("UnknownElement", el)

    def test_key_error_message_lists_known_schemas(self, registry):
        el = etree.fromstring(_VALID_DOCUMENT)
        with pytest.raises(KeyError) as exc_info:
            registry.validate("Missing", el)
        assert "Document" in str(exc_info.value)
