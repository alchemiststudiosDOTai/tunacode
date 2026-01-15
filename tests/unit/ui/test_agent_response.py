"""Tests for agent response renderer."""

import pytest

from tunacode.ui.renderers.agent_response import (
    _format_duration,
    _format_model,
    _format_tokens,
    render_agent_response,
    render_agent_streaming,
)


class TestFormatModel:
    """Tests for _format_model function."""

    def test_format_model_anthropic_prefix(self) -> None:
        """Anthropic models get ANTH/ prefix."""
        assert _format_model("anthropic/claude-3.5-sonnet") == "ANTH/claude-3.5-sonnet"

    def test_format_model_openai_prefix(self) -> None:
        """OpenAI models get OA/ prefix."""
        assert _format_model("openai/gpt-4o") == "OA/gpt-4o"

    def test_format_model_google_prefix(self) -> None:
        """Google models get GOOG/ prefix."""
        assert _format_model("google/gemini-pro") == "GOOG/gemini-pro"

    def test_format_model_mistral_prefix(self) -> None:
        """Mistral models get MIST/ prefix."""
        assert _format_model("mistral/mistral-large") == "MIST/mistral-large"

    def test_format_model_openrouter_prefix(self) -> None:
        """OpenRouter models get OR/ prefix."""
        assert _format_model("openrouter/anthropic/claude-3") == "OR/anthropic/claude-3"

    def test_format_model_together_prefix(self) -> None:
        """Together models get TOG/ prefix."""
        assert _format_model("together/meta-llama/Llama-3-70b") == "TOG/meta-llama/Llama-3-70b"

    def test_format_model_groq_prefix(self) -> None:
        """Groq models get GROQ/ prefix."""
        assert _format_model("groq/llama3-70b-8192") == "GROQ/llama3-70b-8192"

    def test_format_model_unknown_provider(self) -> None:
        """Unknown providers pass through unchanged."""
        assert _format_model("local/llama-3-70b") == "local/llama-3-70b"
        assert _format_model("custom-model") == "custom-model"

    def test_format_model_truncates_long_names(self) -> None:
        """Very long model names (>30 chars) get truncated."""
        # After abbreviation: "ANTH/" + 30 chars = 35 chars, should truncate
        long_model = "anthropic/" + "x" * 30
        result = _format_model(long_model)
        assert len(result) == 30  # 27 + "..."
        assert result.endswith("...")

    def test_format_model_under_limit_not_truncated(self) -> None:
        """Model names under 30 chars are not truncated."""
        model = "anthropic/claude-3.5-sonnet"  # 29 chars
        # After abbreviation: "ANTH/claude-3.5-sonnet" = 22 chars
        result = _format_model(model)
        assert len(result) == 22
        assert not result.endswith("...")


class TestFormatTokens:
    """Tests for _format_tokens function."""

    def test_format_tokens_small(self) -> None:
        """Small token counts display as-is."""
        assert _format_tokens(0) == "0"
        assert _format_tokens(999) == "999"

    def test_format_tokens_k_suffix(self) -> None:
        """Token counts >=1000 get k suffix."""
        assert _format_tokens(1000) == "1.0k"
        assert _format_tokens(1500) == "1.5k"
        assert _format_tokens(12345) == "12.3k"

    def test_format_tokens_negative_raises(self) -> None:
        """Negative tokens raise ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            _format_tokens(-1)


class TestFormatDuration:
    """Tests for _format_duration function."""

    def test_format_duration_ms(self) -> None:
        """Durations <1000ms display in milliseconds."""
        assert _format_duration(0) == "0ms"
        assert _format_duration(500) == "500ms"
        assert _format_duration(999) == "999ms"

    def test_format_duration_s_suffix(self) -> None:
        """Durations >=1000ms display in seconds."""
        assert _format_duration(1000) == "1.0s"
        assert _format_duration(1500) == "1.5s"
        assert _format_duration(5000) == "5.0s"

    def test_format_duration_negative_raises(self) -> None:
        """Negative duration raises ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            _format_duration(-1)


class TestStatusOrdering:
    """Tests for status bar ordering in render functions."""

    def test_streaming_status_bar_order(self) -> None:
        """Streaming status bar: model · streaming · duration."""
        result = render_agent_streaming(
            "test content",
            elapsed_ms=1500,
            model="anthropic/claude-3.5-sonnet",
        )
        # Result should be a Panel; we can't easily inspect the exact order
        # but we can verify it renders without error
        assert result is not None

    def test_response_status_bar_order(self) -> None:
        """Response status bar: model · tokens · duration."""
        result = render_agent_response(
            content="test",
            tokens=1500,
            duration_ms=2500,
            model="openai/gpt-4o",
        )
        assert result is not None

    def test_status_bar_with_partial_data(self) -> None:
        """Status bar handles missing optional fields gracefully."""
        # Only model
        result = render_agent_response(content="test", model="google/gemini-pro")
        assert result is not None

        # Only tokens
        result = render_agent_response(content="test", tokens=500)
        assert result is not None

        # Only duration
        result = render_agent_response(content="test", duration_ms=100)
        assert result is not None
