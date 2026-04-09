import os
import sys
sys.path.insert(0, 'src')

from rag_service.config import get_settings

settings = get_settings()

print("=" * 60)
print("RAG Service Configuration")
print("=" * 60)

print(f"\n[Cloud Completion]")
print(f"  URL: {settings.cloud_completion.url}")
print(f"  Model: {settings.cloud_completion.model}")
print(f"  Timeout: {settings.cloud_completion.timeout}")
print(f"  Auth Token: {settings.cloud_completion.auth_token[:20]}...{settings.cloud_completion.auth_token[-10:] if settings.cloud_completion.auth_token else 'None'}")
print(f"  Max Retries: {settings.cloud_completion.max_retries}")
print(f"  Retry Delay: {settings.cloud_completion.retry_delay}")
print(f"  Enabled: {settings.cloud_completion.enabled}")

print(f"\n[External KB]")
print(f"  Base URL: {settings.external_kb.base_url}")
print(f"  Endpoint: {settings.external_kb.endpoint}")
print(f"  Timeout: {settings.external_kb.timeout}")
print(f"  Enabled: {settings.external_kb.enabled}")
print(f"  Headers: {settings.external_kb.headers}")

print(f"\n[QA]")
print(f"  Enable Query Rewrite: {settings.qa.enable_query_rewrite}")
print(f"  Enable Hallucination Check: {settings.qa.enable_hallucination_check}")
print(f"  Hallucination Threshold: {settings.qa.hallucination_threshold}")
