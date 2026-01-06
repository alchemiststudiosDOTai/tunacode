---
title: anchor — integration tests call real LLM, no mocking
link: real-llm-integration-tests
type: memory_anchors
ontological_relations:
  - relates_to: [[test-headless-cli]]
tags:
  - testing
  - integration
  - principle
created_at: 2026-01-06T15:00:00Z
updated_at: 2026-01-06T15:00:00Z
uuid: 98d4d2cc-cd77-4432-bc57-eeaf930a608e
---
Integration tests marked with `@pytest.mark.integration` intentionally call the REAL LLM API without mocking. This forces the agent to actually work and catches real integration issues that mocks would hide.

If these tests fail, check:
1. API key is set (ANTHROPIC_API_KEY or OPENAI_API_KEY)
2. Network connectivity
3. Model availability

Reference: `tests/test_headless_cli.py::test_needle_in_haystack`
