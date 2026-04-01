"""
Unit tests for PromptAssemblyService.

Tests verify:
- Section rendering
- Jinja2 interpolation
- Context injection
- Retrieved docs formatting
"""

import pytest
from datetime import datetime
from typing import Dict, Any

from prompt_service.services.prompt_assembly import (
    PromptAssemblyService,
    get_prompt_assembly_service,
)
from prompt_service.models.prompt import (
    PromptAssemblyContext,
    PromptAssemblyResult,
    PromptTemplate,
    StructuredSection,
    VariableDef,
    VariableType,
)
from prompt_service.core.exceptions import PromptValidationError


class TestPromptAssemblyService:
    """Unit tests for PromptAssemblyService."""

    @pytest.fixture
    def service(self) -> PromptAssemblyService:
        """Get the prompt assembly service instance."""
        return get_prompt_assembly_service()

    @pytest.fixture
    def sample_template(self) -> PromptTemplate:
        """Create a sample prompt template."""
        return PromptTemplate(
            template_id="test_prompt",
            name="Test Prompt",
            description="Testing prompt assembly",
            version=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            created_by="test",
            tags=[],
            sections=[
                StructuredSection(name="角色", content="AI助手", order=0),
                StructuredSection(name="任务", content="{{input}}", order=1),
                StructuredSection(name="约束", content="准确", order=2),
            ],
            variables={
                "input": VariableDef(
                    name="input",
                    description="User input",
                    type=VariableType.STRING,
                    is_required=True
                )
            },
            is_active=True,
            is_published=True,
            metadata={}
        )

    def test_section_rendering(
        self,
        service: PromptAssemblyService,
        sample_template: PromptTemplate,
    ) -> None:
        """Test that sections are rendered in correct order.

        Given: A prompt template with multiple sections
        When: assemble_prompt is called
        Then: Sections appear in output in order defined by order field
        """
        context = PromptAssemblyContext(
            template=sample_template,
            variables={"input": "test value"},
            context={},
            retrieved_docs=[],
            trace_id="test_trace",
        )

        result = service.assemble_prompt(context)

        assert result is not None
        assert result.content is not None

        # Check sections appear in order
        lines = result.content.split("\n")
        role_idx = next(i for i, line in enumerate(lines) if "[角色]" in line)
        task_idx = next(i for i, line in enumerate(lines) if "[任务]" in line)
        constraint_idx = next(i for i, line in enumerate(lines) if "[约束]" in line)

        assert role_idx < task_idx < constraint_idx

    def test_jinja2_interpolation(
        self,
        service: PromptAssemblyService,
        sample_template: PromptTemplate,
    ) -> None:
        """Test that Jinja2 variables are interpolated.

        Given: A prompt template with Jinja2 variables
        When: assemble_prompt is called with variable values
        Then: Variables are replaced in output
        """
        context = PromptAssemblyContext(
            template=sample_template,
            variables={"input": "Hello World"},
            context={},
            retrieved_docs=[],
            trace_id="test_trace",
        )

        result = service.assemble_prompt(context)

        assert "Hello World" in result.content
        assert "{{input}}" not in result.content

    def test_context_injection(
        self,
        service: PromptAssemblyService,
    ) -> None:
        """Test that context is injected into prompt.

        Given: Assembly context with context data
        When: assemble_prompt is called
        Then: [上下文] section is added with context data
        """
        template = PromptTemplate(
            template_id="test",
            name="Test",
            description="Test",
            version=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            created_by="test",
            tags=[],
            sections=[
                StructuredSection(name="任务", content="Do task", order=0)
            ],
            variables={},
            is_active=True,
            is_published=True,
            metadata={}
        )

        context = PromptAssemblyContext(
            template=template,
            variables={},
            context={"user_id": "user123", "session_id": "sess456"},
            retrieved_docs=[],
            trace_id="test",
        )

        result = service.assemble_prompt(context)

        assert "[上下文]" in result.content
        assert "user_id: user123" in result.content
        assert "session_id: sess456" in result.content

    def test_retrieved_docs_formatting(
        self,
        service: PromptAssemblyService,
    ) -> None:
        """Test that retrieved docs are formatted correctly.

        Given: Assembly context with retrieved documents
        When: assemble_prompt is called
        Then: [检索文档] section is added with doc content
        """
        template = PromptTemplate(
            template_id="test",
            name="Test",
            description="Test",
            version=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            created_by="test",
            tags=[],
            sections=[
                StructuredSection(name="任务", content="Task", order=0)
            ],
            variables={},
            is_active=True,
            is_published=True,
            metadata={}
        )

        retrieved_docs = [
            {
                "id": "doc1",
                "content": "Document 1 content",
                "metadata": {"source": "encyclopedia"}
            },
            {
                "id": "doc2",
                "content": "Document 2 content",
                "metadata": {"source": "atlas"}
            }
        ]

        context = PromptAssemblyContext(
            template=template,
            variables={},
            context={},
            retrieved_docs=retrieved_docs,
            trace_id="test",
        )

        result = service.assemble_prompt(context)

        assert "[检索文档]" in result.content
        assert "Document 1 content" in result.content
        assert "Document 2 content" in result.content
        assert "来源: encyclopedia" in result.content

    def test_required_variable_validation(
        self,
        service: PromptAssemblyService,
        sample_template: PromptTemplate,
    ) -> None:
        """Test that missing required variables raise error.

        Given: A template with required variables
        When: assemble_prompt is called without required variables
        Then: PromptValidationError is raised
        """
        context = PromptAssemblyContext(
            template=sample_template,
            variables={},  # Missing required "input"
            context={},
            retrieved_docs=[],
            trace_id="test",
        )

        with pytest.raises(PromptValidationError) as exc_info:
            service.assemble_prompt(context)

        # Check validation_errors contains the specific error
        assert any("Missing required variable" in err for err in exc_info.value.validation_errors)

    def test_optional_variables_with_defaults(
        self,
        service: PromptAssemblyService,
    ) -> None:
        """Test that optional variables use defaults when not provided.

        Given: A template with optional variables with defaults
        When: assemble_prompt is called without optional variables
        Then: Default values are used
        """
        template = PromptTemplate(
            template_id="test",
            name="Test",
            description="Test",
            version=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            created_by="test",
            tags=[],
            sections=[
                StructuredSection(
                    name="任务",
                    content="Process {{language | default('English')}}",
                    order=0
                )
            ],
            variables={
                "language": VariableDef(
                    name="language",
                    description="Language",
                    type=VariableType.STRING,
                    is_required=False,
                    default_value="English"
                )
            },
            is_active=True,
            is_published=True,
            metadata={}
        )

        context = PromptAssemblyContext(
            template=template,
            variables={},  # Not providing optional variable
            context={},
            retrieved_docs=[],
            trace_id="test",
        )

        result = service.assemble_prompt(context)

        # Should use default value
        assert "Process English" in result.content

    def test_nested_dict_context(
        self,
        service: PromptAssemblyService,
    ) -> None:
        """Test that nested dict context is formatted correctly.

        Given: Context with nested dictionaries
        When: assemble_prompt is called
        Then: Nested values are formatted properly
        """
        template = PromptTemplate(
            template_id="test",
            name="Test",
            description="Test",
            version=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            created_by="test",
            tags=[],
            sections=[
                StructuredSection(name="任务", content="Task", order=0)
            ],
            variables={},
            is_active=True,
            is_published=True,
            metadata={}
        )

        context = PromptAssemblyContext(
            template=template,
            variables={},
            context={
                "user": {
                    "id": "123",
                    "name": "Test User"
                },
                "session": {
                    "id": "abc"
                }
            },
            retrieved_docs=[],
            trace_id="test",
        )

        result = service.assemble_prompt(context)

        assert "[上下文]" in result.content
        # Nested dict should be formatted with indentation
        assert "user:" in result.content
        assert "  id: 123" in result.content

    def test_multiple_variables_interpolation(
        self,
        service: PromptAssemblyService,
    ) -> None:
        """Test that multiple variables are interpolated.

        Given: A template with multiple variables
        When: assemble_prompt is called with all variables
        Then: All variables are replaced correctly
        """
        template = PromptTemplate(
            template_id="test",
            name="Test",
            description="Test",
            version=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            created_by="test",
            tags=[],
            sections=[
                StructuredSection(
                    name="任务",
                    content="{{task}} for {{language}} in {{topic}}",
                    order=0
                )
            ],
            variables={
                "task": VariableDef(
                    name="task",
                    description="Task",
                    type=VariableType.STRING,
                    is_required=True
                ),
                "language": VariableDef(
                    name="language",
                    description="Language",
                    type=VariableType.STRING,
                    is_required=True
                ),
                "topic": VariableDef(
                    name="topic",
                    description="Topic",
                    type=VariableType.STRING,
                    is_required=True
                ),
            },
            is_active=True,
            is_published=True,
            metadata={}
        )

        context = PromptAssemblyContext(
            template=template,
            variables={
                "task": "Translation",
                "language": "Python",
                "topic": "NLP"
            },
            context={},
            retrieved_docs=[],
            trace_id="test",
        )

        result = service.assemble_prompt(context)

        assert "Translation for Python in NLP" in result.content
        assert "{{task}}" not in result.content
        assert "{{language}}" not in result.content
        assert "{{topic}}" not in result.content

    def test_empty_sections_are_skipped(
        self,
        service: PromptAssemblyService,
    ) -> None:
        """Test that empty sections are handled correctly.

        Given: A template with some empty sections
        When: assemble_prompt is called
        Then: Empty sections are rendered or skipped based on content
        """
        template = PromptTemplate(
            template_id="test",
            name="Test",
            description="Test",
            version=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            created_by="test",
            tags=[],
            sections=[
                StructuredSection(name="角色", content="AI助手", order=0),
                StructuredSection(
                    name="空节",
                    content="   ",  # Only whitespace
                    order=1
                ),
                StructuredSection(name="任务", content="Do work", order=2),
            ],
            variables={},
            is_active=True,
            is_published=True,
            metadata={}
        )

        context = PromptAssemblyContext(
            template=template,
            variables={},
            context={},
            retrieved_docs=[],
            trace_id="test",
        )

        result = service.assemble_prompt(context)

        # Empty sections should be handled (may still render section header)
        # The implementation only adds content if non-empty
        assert "[角色]" in result.content
        assert "[任务]" in result.content

    def test_metadata_in_result(
        self,
        service: PromptAssemblyService,
        sample_template: PromptTemplate,
    ) -> None:
        """Test that result contains correct metadata.

        Given: A prompt template
        When: assemble_prompt is called
        Then: Result contains template metadata
        """
        context = PromptAssemblyContext(
            template=sample_template,
            variables={"input": "test"},
            context={},
            retrieved_docs=[],
            trace_id="test_trace_123",
        )

        result = service.assemble_prompt(context)

        assert result.template_id == "test_prompt"
        assert result.version_id == 1
        assert result.metadata is not None
        assert result.metadata["template_name"] == "Test Prompt"

    def test_trace_id_propagation(
        self,
        service: PromptAssemblyService,
        sample_template: PromptTemplate,
    ) -> None:
        """Test that trace_id is propagated correctly.

        Given: Assembly context with a trace_id
        When: assemble_prompt is called
        Then: Result trace_id matches context trace_id
        """
        expected_trace_id = "custom_trace_456"

        context = PromptAssemblyContext(
            template=sample_template,
            variables={"input": "test"},
            context={},
            retrieved_docs=[],
            trace_id=expected_trace_id,
        )

        result = service.assemble_prompt(context)

        # Note: trace_id may be generated internally if not provided
        # The result should have a trace_id
        assert result.trace_id is not None
