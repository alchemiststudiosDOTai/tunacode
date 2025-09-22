import pytest

from tunacode.cli import commands


class TestCommandRegistryFuzzyMatching:
    def test_golden_prefix_matching_preserved(self):
        """Golden: prefix matching remains unchanged (fail-fast if regresses)."""
        registry = commands.CommandRegistry()
        registry.discover_commands()
        matches = registry.find_matching_commands("he")
        assert "help" in matches

    def test_fuzzy_fallback_matches_typo(self):
        """Fuzzy: near-miss should suggest the intended single command."""
        registry = commands.CommandRegistry()
        registry.discover_commands()
        # Intentional typo missing the 'l'
        matches = registry.find_matching_commands("hep")
        # Should offer a fuzzy suggestion for 'help'
        assert "help" in matches
