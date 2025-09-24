"""Characterization tests capturing desired fuzzy completion behavior."""

from pathlib import Path

from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document

from tunacode.cli import commands
from tunacode.ui.completers import CommandCompleter, FileReferenceCompleter


class TestPromptToolkitFuzzy:
    """Ensure CLI completers surface fuzzy matches for near-miss input."""

    def test_fuzzy_suggests_command(self) -> None:
        """Typing a command with a typo should still suggest the intended command."""

        registry = commands.CommandRegistry()
        registry.discover_commands()
        completer = CommandCompleter(command_registry=registry)

        document = Document(text="/hep")
        assert hasattr(document, "text_before_cursor")
        completions = list(completer.get_completions(document, CompleteEvent()))

        assert any(completion.text == "/help" for completion in completions)

    def test_fuzzy_file_reference_prioritizes_files(self, tmp_path: Path) -> None:
        """File completions should offer fuzzy matches prioritizing files before directories."""

        file_path = tmp_path / "test_example.py"
        file_path.write_text("print('example')\n", encoding="utf-8")
        directory_path = tmp_path / "test_examples"
        directory_path.mkdir()

        completer = FileReferenceCompleter()
        reference = f"@{tmp_path}/tst_example.py"
        document = Document(text=reference)
        assert hasattr(document, "get_word_before_cursor")
        completions = list(completer.get_completions(document, CompleteEvent()))

        ordered_text = [completion.text for completion in completions]

        assert ordered_text and ordered_text[0].endswith("test_example.py")

    def test_fuzzy_file_reference_walks_nested_directories(self) -> None:
        """Global fuzzy completions should surface deeper files when matching."""

        completer = FileReferenceCompleter()
        document = Document(text="@mai")
        completions = list(completer.get_completions(document, CompleteEvent()))

        completion_texts = [completion.text for completion in completions]
        print(completion_texts)

        assert any(
            text.endswith("src/tunacode/cli/main.py")
            for text in completion_texts
            if text.endswith(".py")
        )
