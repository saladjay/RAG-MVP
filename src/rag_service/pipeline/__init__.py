"""
Atomic Pipeline for RAG Service.

Orchestrates query processing through discrete, independently executable
steps. Each step reads from and writes to a shared PipelineContext.

Exports: PipelineRunner, PipelineContext, PipelinePolicy, StepCapability, MemoryCapability
"""

from rag_service.pipeline.context import PipelineContext
from rag_service.pipeline.policy import PipelinePolicy
from rag_service.pipeline.protocols import MemoryCapability, StepCapability
from rag_service.pipeline.runner import PipelineRunner

__all__ = [
    "MemoryCapability",
    "PipelineContext",
    "PipelinePolicy",
    "PipelineRunner",
    "StepCapability",
]
