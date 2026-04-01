"""
Integration tests for YAML parser.
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from e2e_test.parsers.yaml_parser import YAMLParser
from e2e_test.core.exceptions import TestFileError


class TestYAMLParser:
    """Test YAML parser functionality."""

    def test_parse_valid_yaml_list(self):
        """Test parsing a valid YAML file with list of test cases."""
        yaml_content = """
- id: test1
  question: What is Python?
  expected_answer: A programming language
  source_docs:
    - doc1
  tags:
    - lang
- id: test2
  question: What is FastAPI?
  source_docs:
    - doc2
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
            parser = YAMLParser()
            test_cases = parser.parse(file_path)

            assert len(test_cases) == 2
            assert test_cases[0].id == "test1"
            assert test_cases[0].question == "What is Python?"
            assert test_cases[0].expected_answer == "A programming language"
            assert test_cases[0].source_docs == ["doc1"]
            assert test_cases[0].tags == ["lang"]
        finally:
            file_path.unlink()

    def test_parse_yaml_dict_with_tests_key(self):
        """Test parsing YAML file with dict containing 'tests' key."""
        yaml_content = """
tests:
  - id: test1
    question: What is Python?
  - id: test2
    question: What is FastAPI?
"""

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".yml",
            delete=False,
            encoding="utf-8"
        ) as f:
            f.write(yaml_content)
            f.flush()
            file_path = Path(f.name)

        try:
            parser = YAMLParser()
            test_cases = parser.parse(file_path)

            assert len(test_cases) == 2
            assert test_cases[0].id == "test1"
            assert test_cases[1].id == "test2"
        finally:
            file_path.unlink()

    def test_parse_yaml_with_all_fields(self):
        """Test parsing YAML with all fields populated."""
        yaml_content = """
- id: test1
  question: Test question
  expected_answer: Test answer
  source_docs:
    - doc1
    - doc2
  tags:
    - tag1
    - tag2
  metadata:
    priority: high
    category: integration
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
            parser = YAMLParser()
            test_cases = parser.parse(file_path)

            assert len(test_cases) == 1
            assert test_cases[0].source_docs == ["doc1", "doc2"]
            assert test_cases[0].tags == ["tag1", "tag2"]
            assert test_cases[0].metadata == {"priority": "high", "category": "integration"}
        finally:
            file_path.unlink()

    def test_parse_yaml_with_single_source_doc_string(self):
        """Test parsing YAML with single source doc as string (not list)."""
        yaml_content = """
- id: test1
  question: Test question
  source_docs: doc1
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
            parser = YAMLParser()
            test_cases = parser.parse(file_path)

            assert len(test_cases) == 1
            assert test_cases[0].source_docs == ["doc1"]
        finally:
            file_path.unlink()

    def test_parse_yaml_with_single_tag_string(self):
        """Test parsing YAML with single tag as string (not list)."""
        yaml_content = """
- id: test1
  question: Test question
  tags: tag1
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
            parser = YAMLParser()
            test_cases = parser.parse(file_path)

            assert len(test_cases) == 1
            assert test_cases[0].tags == ["tag1"]
        finally:
            file_path.unlink()

    def test_parse_empty_yaml_raises_error(self):
        """Test that parsing an empty YAML file raises an error."""
        yaml_content = ""

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
            parser = YAMLParser()
            with pytest.raises(TestFileError, match="empty"):
                parser.parse(file_path)
        finally:
            file_path.unlink()

    def test_parse_yaml_dict_without_tests_key_raises_error(self):
        """Test that parsing dict without 'tests' key raises an error."""
        yaml_content = """
key1: value1
key2: value2
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
            parser = YAMLParser()
            with pytest.raises(TestFileError, match="missing 'tests' key"):
                parser.parse(file_path)
        finally:
            file_path.unlink()

    def test_parse_yaml_with_invalid_type_raises_error(self):
        """Test that parsing YAML with wrong root type raises an error."""
        yaml_content = "just_a_string"

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
            parser = YAMLParser()
            with pytest.raises(TestFileError, match="must be a list or dict"):
                parser.parse(file_path)
        finally:
            file_path.unlink()

    def test_parse_yaml_missing_required_id_raises_error(self):
        """Test that missing 'id' field raises an error."""
        yaml_content = """
- question: What is Python?
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
            parser = YAMLParser()
            with pytest.raises(TestFileError, match="missing required field.*'id'"):
                parser.parse(file_path)
        finally:
            file_path.unlink()

    def test_parse_yaml_missing_required_question_raises_error(self):
        """Test that missing 'question' field raises an error."""
        yaml_content = """
- id: test1
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
            parser = YAMLParser()
            with pytest.raises(TestFileError, match="missing required field.*'question'"):
                parser.parse(file_path)
        finally:
            file_path.unlink()

    def test_parse_yaml_with_no_test_cases_raises_error(self):
        """Test that parsing YAML with empty test list raises an error."""
        yaml_content = """
tests: []
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
            parser = YAMLParser()
            with pytest.raises(TestFileError, match="no test cases"):
                parser.parse(file_path)
        finally:
            file_path.unlink()

    def test_parse_yaml_file_not_found(self):
        """Test that parsing non-existent file raises an error."""
        parser = YAMLParser()
        with pytest.raises(TestFileError, match="File not found"):
            parser.parse(Path("/nonexistent/file.yaml"))
