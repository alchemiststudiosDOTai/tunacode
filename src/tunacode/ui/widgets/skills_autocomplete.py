"""Autocomplete dropdown for `/skills` subcommands and skill names."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from textual.widgets import Input
from textual_autocomplete import AutoComplete, DropdownItem, DropdownItemHit, TargetState

if TYPE_CHECKING:
    from tunacode.skills.models import SkillSummary

SKILLS_COMMAND_PREFIX = "/skills"
SEARCH_SUBCOMMAND = "search"
ROOT_SUBCOMMANDS: tuple[str, ...] = ("clear", "loaded", SEARCH_SUBCOMMAND)


@dataclass(frozen=True, slots=True)
class _SkillsInputState:
    mode: str
    search: str


class SkillsAutoComplete(AutoComplete):
    """Suggest `/skills` actions and available skill names as the user types."""

    def __init__(self, target: Input) -> None:
        super().__init__(target)

    def _align_to_target(self) -> None:
        """Align dropdown above the input bar instead of below."""
        from textual.geometry import Offset, Region, Spacing

        x, y = self.target.cursor_screen_offset
        dropdown = self.option_list
        width, height = dropdown.outer_size

        # Position above the cursor and keep the dropdown constrained to screen bounds.
        x, y, _width, _height = Region(x - 1, y - height - 1, width, height).constrain(
            "inside",
            "none",
            Spacing.all(0),
            self.screen.scrollable_content_region,
        )
        self.absolute_offset = Offset(x, y)

    def _list_skill_summaries(self) -> list[SkillSummary]:
        from tunacode.skills.registry import list_skill_summaries

        return list_skill_summaries()

    def _filter_skill_summaries(
        self, skill_summaries: list[SkillSummary], *, query: str
    ) -> list[SkillSummary]:
        from tunacode.skills.search import filter_skill_summaries

        return filter_skill_summaries(skill_summaries, query=query)

    def get_search_string(self, target_state: TargetState) -> str:
        parsed_state = self._parse_skills_input(target_state)
        if parsed_state is None:
            return ""
        return parsed_state.search

    def should_show_dropdown(self, search_string: str) -> bool:  # noqa: ARG002
        del search_string
        if self.option_list.option_count == 0:
            return False

        target_state = self._get_target_state()
        parsed_state = self._parse_skills_input(target_state)
        if parsed_state is None:
            return False

        return not self._is_exact_completion(parsed_state)

    def get_candidates(self, target_state: TargetState) -> list[DropdownItem]:
        parsed_state = self._parse_skills_input(target_state)
        if parsed_state is None:
            return []

        if parsed_state.mode == SEARCH_SUBCOMMAND:
            return self._skill_candidates(parsed_state.search)

        command_candidates = self._subcommand_candidates(parsed_state.search)
        skill_candidates = self._skill_candidates(parsed_state.search)
        return [*command_candidates, *skill_candidates]

    def apply_completion(self, value: str, state: TargetState) -> None:
        parsed_state = self._parse_skills_input(state)
        if parsed_state is None:
            return

        if value == SEARCH_SUBCOMMAND and parsed_state.mode == "root":
            self.target.value = f"{SKILLS_COMMAND_PREFIX} {SEARCH_SUBCOMMAND} "
            self.target.cursor_position = len(self.target.value)
            return

        command_prefix = self._replacement_prefix(parsed_state.mode)
        self.target.value = f"{command_prefix}{value}"
        self.target.cursor_position = len(self.target.value)

    def _parse_skills_input(self, target_state: TargetState) -> _SkillsInputState | None:
        text_before_cursor = target_state.text[: target_state.cursor_position]
        skills_command_with_space = f"{SKILLS_COMMAND_PREFIX} "
        if not text_before_cursor.startswith(skills_command_with_space):
            return None

        argument_region = text_before_cursor[len(skills_command_with_space) :]
        if not argument_region:
            return _SkillsInputState(mode="root", search="")

        search_prefix = f"{SEARCH_SUBCOMMAND} "
        if argument_region.startswith(search_prefix):
            return _SkillsInputState(
                mode=SEARCH_SUBCOMMAND,
                search=argument_region[len(search_prefix) :],
            )

        if " " in argument_region:
            return None

        return _SkillsInputState(mode="root", search=argument_region)

    def _is_exact_completion(self, parsed_state: _SkillsInputState) -> bool:
        normalized_search = parsed_state.search.casefold().strip()
        if not normalized_search:
            return False

        if parsed_state.mode == SEARCH_SUBCOMMAND:
            return any(
                skill_summary.name.casefold() == normalized_search
                for skill_summary in self._list_skill_summaries()
            )

        if normalized_search in ROOT_SUBCOMMANDS:
            return True

        return any(
            skill_summary.name.casefold() == normalized_search
            for skill_summary in self._list_skill_summaries()
        )

    def _subcommand_candidates(self, search: str) -> list[DropdownItem]:
        normalized_search = search.casefold()
        matching_subcommands = [
            subcommand
            for subcommand in ROOT_SUBCOMMANDS
            if subcommand.startswith(normalized_search)
        ]
        return [DropdownItem(main=subcommand) for subcommand in matching_subcommands]

    def _skill_candidates(self, search: str) -> list[DropdownItem]:
        skill_summaries = self._list_skill_summaries()
        matching_summaries = self._filter_skill_summaries(skill_summaries, query=search)
        return [DropdownItem(main=skill_summary.name) for skill_summary in matching_summaries]

    def get_matches(
        self,
        target_state: TargetState,
        candidates: list[DropdownItem],
        search_string: str,
    ) -> list[DropdownItem]:
        del target_state
        if not search_string:
            return candidates

        ordered_matches: list[DropdownItem] = []
        for candidate in candidates:
            score, offsets = self.match(search_string, candidate.value)
            if score <= 0:
                continue

            highlighted_main = self.apply_highlights(candidate.main, offsets)
            ordered_matches.append(
                DropdownItemHit(
                    main=highlighted_main,
                    prefix=candidate.prefix,
                    id=candidate.id,
                    disabled=candidate.disabled,
                )
            )

        return ordered_matches

    def _replacement_prefix(self, mode: str) -> str:
        if mode == SEARCH_SUBCOMMAND:
            return f"{SKILLS_COMMAND_PREFIX} {SEARCH_SUBCOMMAND} "
        return f"{SKILLS_COMMAND_PREFIX} "
