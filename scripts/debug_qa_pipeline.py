"""Debug QA Pipeline initialization and execution."""

import asyncio
import traceback


async def debug_qa_pipeline():
    """Debug QA pipeline execution."""
    print("=" * 60)
    print("Debug QA Pipeline")
    print("=" * 60)

    try:
        # Import and initialize
        print("\n[1] Importing modules...")
        from rag_service.capabilities.qa_pipeline import (
            QAPipelineCapability,
            QAPipelineInput,
        )
        from rag_service.capabilities.external_kb_query import ExternalKBQueryCapability
        from rag_service.api.qa_schemas import QAContext, QAOptions

        print("[1] Imports successful")

        # Get settings
        print("\n[2] Loading settings...")
        from rag_service.config import get_settings
        settings = get_settings()
        print(f"[2] Settings loaded")
        print(f"    - QA config: enable_query_rewrite={settings.qa.enable_query_rewrite}")
        print(f"    - QA config: hallucination_threshold={settings.qa.hallucination_threshold}")
        print(f"    - QA config: max_regen_attempts={settings.qa.max_regen_attempts}")

        # Initialize capability
        print("\n[3] Initializing QA Pipeline Capability...")
        qa_capability = QAPipelineCapability(
            external_kb_capability=ExternalKBQueryCapability(),
            model_inference_capability=None,
        )
        print("[3] QA Pipeline Capability initialized")

        # Create input
        print("\n[4] Creating pipeline input...")
        pipeline_input = QAPipelineInput(
            query="2025年春节放假共计几天？",
            context=QAContext(
                company_id="N000131",
                file_type="PublicDocDispatch"
            ),
            options=QAOptions(
                enable_query_rewrite=False,
                enable_hallucination_check=False,
                top_k=3
            ),
            trace_id="debug123",
        )
        print("[4] Pipeline input created")

        # Execute
        print("\n[5] Executing pipeline...")
        result = await qa_capability.execute(pipeline_input)
        print("[5] Pipeline execution completed")

        print(f"\n[SUCCESS] Answer: {result.answer[:200]}...")
        print(f"Sources: {len(result.sources)}")

    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}")
        print("\nTraceback:")
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(debug_qa_pipeline())
