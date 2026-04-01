"""
Integration tests for CSV parser.
"""

import tempfile
from pathlib import Path

import pytest

from e2e_test.parsers.csv_parser import CSVParser
from e2e_test.core.exceptions import TestFileError


class TestCSVParser:
    """Test CSV parser functionality."""

    def test_parse_valid_csv_file(self):
        """Test parsing a valid CSV file with test cases."""
        csv_content = """id,question,expected_answer,source_docs,tags
test1,What is Python?,A programming language,doc1,lang
test2,What is FastAPI?,A web framework,doc2,web"""

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
            parser = CSVParser()
            test_cases = parser.parse(file_path)

            assert len(test_cases) == 2
            assert test_cases[0].id == "test1"
            assert test_cases[0].question == "What is Python?"
            assert test_cases[0].expected_answer == "A programming language"
            assert test_cases[0].source_docs == ["doc1"]
            assert test_cases[0].tags == ["lang"]

            assert test_cases[1].id == "test2"
            assert test_cases[1].question == "What is FastAPI?"
            assert test_cases[1].source_docs == ["doc2"]
        finally:
            file_path.unlink()

    def test_parse_csv_with_multiple_source_docs(self):
        """Test parsing CSV with semicolon-separated source docs."""
        csv_content = """id,question,source_docs
test1,Question 1,doc1;doc2;doc3"""

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
            parser = CSVParser()
            test_cases = parser.parse(file_path)

            assert len(test_cases) == 1
            assert test_cases[0].source_docs == ["doc1", "doc2", "doc3"]
        finally:
            file_path.unlink()

    def test_parse_csv_with_comma_separated_values(self):
        """Test parsing CSV with comma-separated source docs (quoted)."""
        csv_content = '''id,question,source_docs
test1,Question 1,"doc1,doc2,doc3"'''

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
            parser = CSVParser()
            test_cases = parser.parse(file_path)

            assert len(test_cases) == 1
            assert test_cases[0].source_docs == ["doc1", "doc2", "doc3"]
        finally:
            file_path.unlink()

    def test_parse_csv_with_empty_optional_fields(self):
        """Test parsing CSV with empty optional fields."""
        csv_content = """id,question,expected_answer,source_docs,tags
test1,Question 1,,,"""

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
            parser = CSVParser()
            test_cases = parser.parse(file_path)

            assert len(test_cases) == 1
            assert test_cases[0].expected_answer is None
            assert test_cases[0].source_docs == []
            assert test_cases[0].tags == []
        finally:
            file_path.unlink()

    def test_parse_csv_with_quoted_fields(self):
        """Test parsing CSV with quoted fields containing commas."""
        csv_content = """id,question,expected_answer
test1,"What is the capital of France?","Paris, the capital city" """

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
            parser = CSVParser()
            test_cases = parser.parse(file_path)

            assert len(test_cases) == 1
            assert test_cases[0].question == "What is the capital of France?"
            assert test_cases[0].expected_answer == "Paris, the capital city"
        finally:
            file_path.unlink()

    def test_parse_csv_with_utf8_bom(self):
        """Test parsing CSV file with UTF-8 BOM."""
        csv_content = """id,question
test1,Question 1"""

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".csv",
            delete=False,
            encoding="utf-8-sig"
        ) as f:
            f.write(csv_content)
            f.flush()
            file_path = Path(f.name)

        try:
            parser = CSVParser()
            test_cases = parser.parse(file_path)

            assert len(test_cases) == 1
            assert test_cases[0].id == "test1"
        finally:
            file_path.unlink()

    def test_parse_empty_csv_raises_error(self):
        """Test that parsing an empty CSV file raises an error."""
        csv_content = """id,question"""

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
            parser = CSVParser()
            with pytest.raises(TestFileError, match="empty"):
                parser.parse(file_path)
        finally:
            file_path.unlink()

    def test_parse_csv_missing_required_column(self):
        """Test that CSV missing required column raises an error."""
        csv_content = """id
test1"""

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
            parser = CSVParser()
            with pytest.raises(TestFileError, match="missing required columns"):
                parser.parse(file_path)
        finally:
            file_path.unlink()

    def test_parse_csv_empty_id_raises_error(self):
        """Test that empty ID in CSV raises an error."""
        csv_content = """id,question
,Question 1"""

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
            parser = CSVParser()
            with pytest.raises(TestFileError, match="'id' column is empty"):
                parser.parse(file_path)
        finally:
            file_path.unlink()

    def test_parse_csv_empty_question_raises_error(self):
        """Test that empty question in CSV raises an error."""
        csv_content = """id,question
test1,"""

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
            parser = CSVParser()
            with pytest.raises(TestFileError, match="'question' column is empty"):
                parser.parse(file_path)
        finally:
            file_path.unlink()

    def test_parse_csv_file_not_found(self):
        """Test that parsing non-existent file raises an error."""
        parser = CSVParser()
        with pytest.raises(TestFileError, match="File not found"):
            parser.parse(Path("/nonexistent/file.csv"))
