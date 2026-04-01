"""
Integration tests for Markdown parser.
"""

import tempfile
from pathlib import Path

import pytest

from e2e_test.parsers.md_parser import MDParser
from e2e_test.core.exceptions import TestFileError


class TestMDParser:
    """Test Markdown parser functionality."""

    def test_parse_markdown_with_yaml_code_block(self):
        """Test parsing markdown with fenced YAML code blocks."""
        md_content = """# Test Document

This is a test document.

```yaml
- id: test1
  question: What is Python?
  expected_answer: A programming language
  source_docs:
    - doc1
  tags:
    - lang
```

Some more text here.

```yaml
- id: test2
  question: What is FastAPI?
  source_docs:
    - doc2
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
            parser = MDParser()
            test_cases = parser.parse(file_path)

            assert len(test_cases) == 2
            assert test_cases[0].id == "test1"
            assert test_cases[0].question == "What is Python?"
            assert test_cases[0].expected_answer == "A programming language"
            assert test_cases[0].source_docs == ["doc1"]
            assert test_cases[0].tags == ["lang"]
        finally:
            file_path.unlink()

    def test_parse_markdown_with_tests_key_in_block(self):
        """Test parsing markdown with dict containing 'tests' key in code block."""
        md_content = """# Tests

```yaml
tests:
  - id: test1
    question: What is Python?
  - id: test2
    question: What is FastAPI?
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
            parser = MDParser()
            test_cases = parser.parse(file_path)

            assert len(test_cases) == 2
            assert test_cases[0].id == "test1"
            assert test_cases[1].id == "test2"
        finally:
            file_path.unlink()

    def test_parse_markdown_with_single_test_case_in_block(self):
        """Test parsing markdown with single test case dict (not list) in code block."""
        md_content = """# Test

```yaml
id: test1
question: What is Python?
expected_answer: A programming language
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
            parser = MDParser()
            test_cases = parser.parse(file_path)

            assert len(test_cases) == 1
            assert test_cases[0].id == "test1"
        finally:
            file_path.unlink()

    def test_parse_markdown_with_markdown_extension(self):
        """Test parsing .markdown file extension."""
        md_content = """# Tests

```yaml
- id: test1
  question: What is Python?
```
"""

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".markdown",
            delete=False,
            encoding="utf-8"
        ) as f:
            f.write(md_content)
            f.flush()
            file_path = Path(f.name)

        try:
            parser = MDParser()
            test_cases = parser.parse(file_path)

            assert len(test_cases) == 1
        finally:
            file_path.unlink()

    def test_parse_markdown_with_multiple_blocks(self):
        """Test parsing markdown with multiple YAML blocks."""
        md_content = """# Test Suite

## Group 1

```yaml
- id: test1
  question: Question 1
```

## Group 2

```yaml
- id: test2
  question: Question 2
```

## Group 3

```yaml
- id: test3
  question: Question 3
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
            parser = MDParser()
            test_cases = parser.parse(file_path)

            assert len(test_cases) == 3
            assert [tc.id for tc in test_cases] == ["test1", "test2", "test3"]
        finally:
            file_path.unlink()

    def test_parse_markdown_with_all_fields(self):
        """Test parsing markdown with all test case fields."""
        md_content = """# Complete Test

```yaml
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
            parser = MDParser()
            test_cases = parser.parse(file_path)

            assert len(test_cases) == 1
            assert test_cases[0].source_docs == ["doc1", "doc2"]
            assert test_cases[0].tags == ["tag1", "tag2"]
            assert test_cases[0].metadata == {"priority": "high", "category": "integration"}
        finally:
            file_path.unlink()

    def test_parse_markdown_skips_empty_yaml_blocks(self):
        """Test that empty YAML blocks are skipped."""
        md_content = """# Tests

```yaml
- id: test1
  question: Question 1
```

Some text.

```yaml

```

```yaml
- id: test2
  question: Question 2
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
            parser = MDParser()
            test_cases = parser.parse(file_path)

            assert len(test_cases) == 2
            assert test_cases[0].id == "test1"
            assert test_cases[1].id == "test2"
        finally:
            file_path.unlink()

    def test_parse_markdown_with_no_yaml_blocks_raises_error(self):
        """Test that markdown without YAML blocks raises an error."""
        md_content = """# Just Text

This is just markdown text with no code blocks.
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
            parser = MDParser()
            with pytest.raises(TestFileError, match="No YAML code blocks found"):
                parser.parse(file_path)
        finally:
            file_path.unlink()

    def test_parse_markdown_with_invalid_yaml_raises_error(self):
        """Test that invalid YAML in code block raises an error."""
        md_content = """# Tests

```yaml
- id: test1
  question: What is Python?
  expected_answer: [unclosed bracket
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
            parser = MDParser()
            # This might actually parse correctly, so let's use truly invalid YAML
            with pytest.raises(TestFileError):
                parser.parse(file_path)
        finally:
            file_path.unlink()

    def test_parse_markdown_missing_required_id_in_block(self):
        """Test that missing 'id' field raises an error."""
        md_content = """# Tests

```yaml
- question: What is Python?
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
            parser = MDParser()
            with pytest.raises(TestFileError, match="missing required field.*'id'"):
                parser.parse(file_path)
        finally:
            file_path.unlink()

    def test_parse_markdown_missing_required_question_in_block(self):
        """Test that missing 'question' field raises an error."""
        md_content = """# Tests

```yaml
- id: test1
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
            parser = MDParser()
            with pytest.raises(TestFileError, match="missing required field.*'question'"):
                parser.parse(file_path)
        finally:
            file_path.unlink()

    def test_parse_markdown_file_not_found(self):
        """Test that parsing non-existent file raises an error."""
        parser = MDParser()
        with pytest.raises(TestFileError, match="File not found"):
            parser.parse(Path("/nonexistent/file.md"))
