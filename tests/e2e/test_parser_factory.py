"""
Integration tests for Parser factory.
"""

import tempfile
from pathlib import Path

import pytest

from e2e_test.parsers.factory import ParserFactory
from e2e_test.parsers.base import Parser
from e2e_test.parsers.json_parser import JSONParser
from e2e_test.parsers.csv_parser import CSVParser
from e2e_test.parsers.yaml_parser import YAMLParser
from e2e_test.parsers.md_parser import MDParser
from e2e_test.models.file_format import FileFormat
from e2e_test.core.exceptions import TestFileError


class TestParserFactory:
    """Test parser factory functionality."""

    def test_create_parser_for_json_file(self):
        """Test factory creates JSONParser for .json files."""
        file_path = Path("test.json")
        parser = ParserFactory.create_parser(file_path)

        assert isinstance(parser, JSONParser)
        assert isinstance(parser, Parser)

    def test_create_parser_for_json_uppercase(self):
        """Test factory handles uppercase .JSON extension."""
        file_path = Path("test.JSON")
        parser = ParserFactory.create_parser(file_path)

        assert isinstance(parser, JSONParser)

    def test_create_parser_for_csv_file(self):
        """Test factory creates CSVParser for .csv files."""
        file_path = Path("test.csv")
        parser = ParserFactory.create_parser(file_path)

        assert isinstance(parser, CSVParser)
        assert isinstance(parser, Parser)

    def test_create_parser_for_yaml_file(self):
        """Test factory creates YAMLParser for .yaml files."""
        file_path = Path("test.yaml")
        parser = ParserFactory.create_parser(file_path)

        assert isinstance(parser, YAMLParser)
        assert isinstance(parser, Parser)

    def test_create_parser_for_yml_file(self):
        """Test factory creates YAMLParser for .yml files."""
        file_path = Path("test.yml")
        parser = ParserFactory.create_parser(file_path)

        assert isinstance(parser, YAMLParser)

    def test_create_parser_for_md_file(self):
        """Test factory creates MDParser for .md files."""
        file_path = Path("test.md")
        parser = ParserFactory.create_parser(file_path)

        assert isinstance(parser, MDParser)
        assert isinstance(parser, Parser)

    def test_create_parser_for_markdown_file(self):
        """Test factory creates MDParser for .markdown files."""
        file_path = Path("test.markdown")
        parser = ParserFactory.create_parser(file_path)

        assert isinstance(parser, MDParser)

    def test_create_parser_for_unsupported_format_raises_error(self):
        """Test that unsupported file format raises an error."""
        file_path = Path("test.txt")
        with pytest.raises(TestFileError, match="Unsupported file extension"):
            ParserFactory.create_parser(file_path)

    def test_create_parser_for_no_extension_raises_error(self):
        """Test that file without extension raises an error."""
        file_path = Path("testfile")
        with pytest.raises(TestFileError, match="Unsupported file extension"):
            ParserFactory.create_parser(file_path)

    def test_get_supported_extensions(self):
        """Test getting list of supported extensions."""
        extensions = ParserFactory.get_supported_extensions()

        assert isinstance(extensions, list)
        assert ".json" in extensions
        assert ".csv" in extensions
        assert ".yaml" in extensions
        assert ".yml" in extensions
        assert ".md" in extensions
        assert ".markdown" in extensions

    def test_is_supported_for_json(self):
        """Test is_supported returns True for JSON files."""
        assert ParserFactory.is_supported(Path("test.json")) is True

    def test_is_supported_for_csv(self):
        """Test is_supported returns True for CSV files."""
        assert ParserFactory.is_supported(Path("test.csv")) is True

    def test_is_supported_for_yaml(self):
        """Test is_supported returns True for YAML files."""
        assert ParserFactory.is_supported(Path("test.yaml")) is True
        assert ParserFactory.is_supported(Path("test.yml")) is True

    def test_is_supported_for_markdown(self):
        """Test is_supported returns True for Markdown files."""
        assert ParserFactory.is_supported(Path("test.md")) is True
        assert ParserFactory.is_supported(Path("test.markdown")) is True

    def test_is_supported_for_unsupported(self):
        """Test is_supported returns False for unsupported files."""
        assert ParserFactory.is_supported(Path("test.txt")) is False
        assert ParserFactory.is_supported(Path("test.pdf")) is False
        assert ParserFactory.is_supported(Path("testfile")) is False

    def test_parse_json_file_through_factory(self):
        """Test end-to-end parsing of JSON file through factory."""
        json_content = """[
    {"id": "test1", "question": "What is Python?"},
    {"id": "test2", "question": "What is FastAPI?"}
]"""

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            delete=False,
            encoding="utf-8"
        ) as f:
            f.write(json_content)
            f.flush()
            file_path = Path(f.name)

        try:
            parser = ParserFactory.create_parser(file_path)
            test_cases = parser.parse(file_path)

            assert len(test_cases) == 2
            assert test_cases[0].id == "test1"
            assert test_cases[1].id == "test2"
        finally:
            file_path.unlink()

    def test_parse_csv_file_through_factory(self):
        """Test end-to-end parsing of CSV file through factory."""
        csv_content = """id,question
test1,What is Python?
test2,What is FastAPI?"""

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".csv",
            delete=False,
            encoding="utf-8"
        ) as f:
            f.write(csv_content)
            f.flush()
            file_path = Path(f.name)

        try:
            parser = ParserFactory.create_parser(file_path)
            test_cases = parser.parse(file_path)

            assert len(test_cases) == 2
            assert test_cases[0].id == "test1"
            assert test_cases[1].id == "test2"
        finally:
            file_path.unlink()

    def test_parse_yaml_file_through_factory(self):
        """Test end-to-end parsing of YAML file through factory."""
        yaml_content = """
- id: test1
  question: What is Python?
- id: test2
  question: What is FastAPI?
"""

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".yaml",
            delete=False,
            encoding="utf-8"
        ) as f:
            f.write(yaml_content)
            f.flush()
            file_path = Path(f.name)

        try:
            parser = ParserFactory.create_parser(file_path)
            test_cases = parser.parse(file_path)

            assert len(test_cases) == 2
            assert test_cases[0].id == "test1"
            assert test_cases[1].id == "test2"
        finally:
            file_path.unlink()

    def test_parse_markdown_file_through_factory(self):
        """Test end-to-end parsing of Markdown file through factory."""
        md_content = """# Tests

```yaml
- id: test1
  question: What is Python?
```
"""

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".md",
            delete=False,
            encoding="utf-8"
        ) as f:
            f.write(md_content)
            f.flush()
            file_path = Path(f.name)

        try:
            parser = ParserFactory.create_parser(file_path)
            test_cases = parser.parse(file_path)

            assert len(test_cases) == 1
            assert test_cases[0].id == "test1"
        finally:
            file_path.unlink()
