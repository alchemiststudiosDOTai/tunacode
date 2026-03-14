"""End-to-end tool tests driven via tmux.

Launches tunacode in a real tmux session, sends prompts, and verifies that each
tool executes by checking tool-specific output or side effects.

These are true system tests -- they exercise the full stack (TUI, agent loop,
tool dispatch, rendering). They require a live API key and tmux.
"""

import os
import shlex
import shutil
import subprocess
import tempfile
import time
import uuid
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TMUX_BINARY = "tmux"
SESSION_PREFIX = "tunatest"
DEFAULT_TIMEOUT_SECONDS = 90
POLL_INTERVAL_SECONDS = 2
STARTUP_READY_TIMEOUT_SECONDS = 30
STARTUP_POLL_INTERVAL_SECONDS = 0.5
TMUX_HISTORY_LINES = "-10000"
REPO_ROOT = Path(__file__).resolve().parents[3]
VENV_DIR = REPO_ROOT / ".venv"
API_KEY_ENV_VAR = "MINIMAX_API_KEY"
TEST_API_KEY_ENV_VAR = "TUNACODE_TEST_API_KEY"
RUN_TMUX_TESTS_ENV_VAR = "TUNACODE_RUN_TMUX_TESTS"
TEST_READY_FILE_ENV_VAR = "TUNACODE_TEST_READY_FILE"

# ---------------------------------------------------------------------------
# Markers & skip guards
# ---------------------------------------------------------------------------

_missing_tmux = not shutil.which(TMUX_BINARY)
_missing_tmux_env_vars = [
    env_var
    for env_var in (RUN_TMUX_TESTS_ENV_VAR, TEST_API_KEY_ENV_VAR)
    if not os.environ.get(env_var)
]
_missing_tmux_env_reason = (
    "tmux suite is opt-in; set " + ", ".join(_missing_tmux_env_vars)
    if _missing_tmux_env_vars
    else ""
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.tmux,
    pytest.mark.skipif(_missing_tmux, reason="tmux is not installed"),
    pytest.mark.skipif(bool(_missing_tmux_env_vars), reason=_missing_tmux_env_reason),
    pytest.mark.timeout(DEFAULT_TIMEOUT_SECONDS),
]


# ---------------------------------------------------------------------------
# TmuxSession helper
# ---------------------------------------------------------------------------


class TmuxSession:
    """Manage a detached tmux session running tunacode."""

    def __init__(self, name: str, *, working_directory: Path | None = None) -> None:
        self.name = name
        self.working_directory = working_directory
        self._temp_dir = Path(tempfile.mkdtemp(prefix=f"{SESSION_PREFIX}_"))
        self.ready_file = self._temp_dir / "ready.txt"

    # -- tmux primitives -----------------------------------------------------

    def _run_tmux(self, *args: str, check: bool = True) -> str:
        result = subprocess.run(
            [TMUX_BINARY, *args],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if check and result.returncode != 0:
            raise RuntimeError(
                f"tmux {' '.join(args)} failed (rc={result.returncode}): {result.stderr}"
            )
        return result.stdout

    def start(self) -> None:
        """Create a detached session and launch tunacode inside it."""
        self.ready_file.parent.mkdir(parents=True, exist_ok=True)
        self.ready_file.unlink(missing_ok=True)

        launch_parts: list[str] = []
        if self.working_directory is not None:
            quoted_working_directory = shlex.quote(str(self.working_directory))
            launch_parts.append(f"cd {quoted_working_directory}")

        launch_parts.extend(
            [
                f"export {TEST_READY_FILE_ENV_VAR}={shlex.quote(str(self.ready_file))}",
                f"export {API_KEY_ENV_VAR}={shlex.quote(os.environ[TEST_API_KEY_ENV_VAR])}",
                f"source {VENV_DIR / 'bin' / 'activate'}",
                "tunacode",
            ]
        )
        shell_cmd = " && ".join(launch_parts)
        self._run_tmux("new-session", "-d", "-s", self.name, "-x", "220", "-y", "50", shell_cmd)

        try:
            deadline = time.monotonic() + STARTUP_READY_TIMEOUT_SECONDS
            while time.monotonic() < deadline:
                if self.ready_file.is_file():
                    return
                time.sleep(STARTUP_POLL_INTERVAL_SECONDS)

            diagnostics = self._startup_diagnostics()
        except Exception:
            self.kill()
            raise

        self.kill()
        raise TimeoutError(self._build_startup_timeout_message(diagnostics))

    def _build_startup_timeout_message(self, diagnostics: str) -> str:
        """Build the startup timeout error message."""
        return f"Timed out waiting for tunacode tmux session readiness file.\n{diagnostics}"

    def _startup_diagnostics(self) -> str:
        """Collect pane and ready-file diagnostics for startup failures."""
        try:
            pane_output = self.capture()
        except (RuntimeError, subprocess.TimeoutExpired) as exc:  # pragma: no cover
            pane_output = f"<capture failed: {exc}>"
        ready_exists = self.ready_file.exists()
        ready_contents = self.ready_file.read_text(encoding="utf-8") if ready_exists else ""
        return (
            f"session={self.name}\n"
            f"ready_file={self.ready_file}\n"
            f"ready_file_exists={ready_exists}\n"
            f"ready_file_contents={ready_contents!r}\n"
            f"pane_capture:\n{pane_output}"
        )

    def kill(self) -> None:
        """Kill the tmux session (ignore errors if already dead)."""
        self._run_tmux("kill-session", "-t", self.name, check=False)
        shutil.rmtree(self._temp_dir, ignore_errors=True)

    def send(self, text: str) -> None:
        """Type *text* followed by Enter into the session."""
        self._run_tmux("send-keys", "-t", self.name, text, "Enter")

    def capture(self) -> str:
        """Return pane contents including recent scrollback history."""
        return self._run_tmux("capture-pane", "-t", self.name, "-p", "-S", TMUX_HISTORY_LINES)


@contextmanager
def tmux_session(
    *,
    working_directory: Path | None = None,
) -> Generator[TmuxSession, None, None]:
    """Context manager: spin up a tunacode tmux session, tear it down on exit."""
    name = f"{SESSION_PREFIX}_{uuid.uuid4().hex[:8]}"
    session = TmuxSession(name, working_directory=working_directory)
    session.start()
    try:
        yield session
    finally:
        session.kill()


# ---------------------------------------------------------------------------
# Polling helpers
# ---------------------------------------------------------------------------


def wait_for_capture(
    session: TmuxSession,
    predicate: Callable[[str], bool],
    *,
    description: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Poll the pane until *predicate* matches. Returns captured output."""
    deadline = time.monotonic() + timeout
    last_output = ""
    while time.monotonic() < deadline:
        output = session.capture()
        last_output = output
        if predicate(output):
            return output
        time.sleep(POLL_INTERVAL_SECONDS)
    raise TimeoutError(
        f"Timed out after {timeout}s waiting for {description}.\n"
        f"Last capture:\n{last_output or session.capture()}"
    )


STABLE_CAPTURE_POLLS = 2


def output_contains_all(output: str, *needles: str) -> bool:
    """Return True when all *needles* are present in *output*."""
    return all(needle in output for needle in needles)


def output_contains_in_order(output: str, *needles: str) -> bool:
    """Return True when all *needles* appear in *output* in the given order."""
    start_index = 0
    for needle in needles:
        match_index = output.find(needle, start_index)
        if match_index == -1:
            return False
        start_index = match_index + len(needle)
    return True


def wait_for_stable_capture(
    session: TmuxSession,
    predicate: Callable[[str], bool],
    *,
    description: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    initial_output: str | None = None,
) -> str:
    """Poll until matching pane output stops changing across consecutive captures."""
    deadline = time.monotonic() + timeout
    last_output = initial_output or session.capture()
    stable_polls = 0
    while time.monotonic() < deadline:
        time.sleep(POLL_INTERVAL_SECONDS)
        output = session.capture()
        if not predicate(output):
            last_output = output
            stable_polls = 0
            continue
        if output == last_output:
            stable_polls += 1
            if stable_polls >= STABLE_CAPTURE_POLLS:
                return output
        else:
            last_output = output
            stable_polls = 0
    raise TimeoutError(
        f"Timed out after {timeout}s waiting for stable {description}.\n"
        f"Last capture:\n{last_output or session.capture()}"
    )


def wait_for_capture_then_stable(
    session: TmuxSession,
    predicate: Callable[[str], bool],
    *,
    description: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Wait for a matching capture, then for that matching state to settle."""
    deadline = time.monotonic() + timeout
    matched_output = wait_for_capture(
        session,
        predicate,
        description=description,
        timeout=max(0.0, deadline - time.monotonic()),
    )
    return wait_for_stable_capture(
        session,
        predicate,
        description=description,
        timeout=max(0.0, deadline - time.monotonic()),
        initial_output=matched_output,
    )


def send_and_wait_for_completion(
    session: TmuxSession,
    prompt: str,
    *,
    description: str,
    pane_predicate: Callable[[str], bool] | None = None,
    side_effect_predicate: Callable[[], bool] | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Send a request, wait for expected evidence, then wait for the pane to settle."""
    baseline = session.capture()
    session.send(prompt)

    def request_completed(output: str) -> bool:
        return (
            output != baseline
            and (pane_predicate(output) if pane_predicate is not None else True)
            and (side_effect_predicate() if side_effect_predicate is not None else True)
        )

    return wait_for_capture_then_stable(
        session,
        request_completed,
        description=description,
        timeout=timeout,
    )


# ---------------------------------------------------------------------------
# Tests -- one per tool
# ---------------------------------------------------------------------------


def test_bash_tool() -> None:
    """bash tool: run a command and verify rendered stdout."""
    marker = f"hello-{uuid.uuid4().hex[:8]}"
    with tmux_session() as s:
        output = send_and_wait_for_completion(
            s,
            "You MUST call the bash tool. Run: "
            f"printf {marker}. Do not answer until the tool runs.",
            description="bash tool stdout",
            pane_predicate=lambda pane: output_contains_all(pane, "stdout:", marker),
        )
        assert marker in output, f"Expected {marker!r} in output:\n{output}"


def test_read_file_tool(tmp_path: Path) -> None:
    """read_file tool: read a temp file and verify its unique contents."""
    target = tmp_path / f"tunatest_read_{uuid.uuid4().hex[:8]}.txt"
    marker = f"read-marker-{uuid.uuid4().hex}"
    target.write_text(f"alpha\n{marker}\nomega\n")

    with tmux_session() as s:
        output = send_and_wait_for_completion(
            s,
            f"You MUST call the read_file tool. Read {target}. Do not answer until the tool runs.",
            description="read_file tool output",
            pane_predicate=lambda pane: marker in pane,
        )
        assert marker in output, f"Expected {marker!r} in output:\n{output}"


def test_write_file_tool() -> None:
    """write_file tool: create a temp file and verify it on disk."""
    target = Path(f"/tmp/tunatest_write_{uuid.uuid4().hex[:8]}.txt")
    content_marker = f"hello-from-tunacode-{uuid.uuid4().hex[:8]}"
    try:
        with tmux_session() as s:
            send_and_wait_for_completion(
                s,
                f"You MUST call the write_file tool. Create {target} with content "
                f'"{content_marker}". Do not answer until the tool runs.',
                description="write_file side effect",
                side_effect_predicate=lambda: target.exists()
                and content_marker in target.read_text(encoding="utf-8"),
            )
            assert content_marker in target.read_text(encoding="utf-8"), (
                f"File contents do not contain marker: {target.read_text(encoding='utf-8')!r}"
            )
    finally:
        target.unlink(missing_ok=True)


def test_hashline_edit_tool(tmp_path: Path) -> None:
    """hashline_edit tool: read then edit a pre-created file."""
    target = tmp_path / f"tunatest_edit_{uuid.uuid4().hex[:8]}.txt"
    original_line = "color = red"
    expected_line = "color = blue"
    try:
        target.write_text(original_line, encoding="utf-8")
        with tmux_session() as s:
            send_and_wait_for_completion(
                s,
                "You MUST call read_file, then hashline_edit. "
                f"Read {target}, then change 'color = red' to 'color = blue'. "
                "Do not answer until both tools run.",
                description="hashline_edit side effect",
                side_effect_predicate=lambda: target.exists()
                and expected_line in target.read_text(encoding="utf-8"),
            )
            updated = target.read_text(encoding="utf-8")
            assert expected_line in updated, f"Expected {expected_line!r} in:\n{updated}"
    finally:
        target.unlink(missing_ok=True)


def test_discover_tool() -> None:
    """discover tool: search for a known tool implementation and verify structured output."""
    with tmux_session() as s:
        output = send_and_wait_for_completion(
            s,
            "You MUST call the discover tool. Query: write_file tool implementation. "
            "Do not answer until the tool runs.",
            description="discover tool output",
            pane_predicate=lambda pane: output_contains_all(pane, "scanned:", "write_file.py"),
        )
        assert "scanned:" in output, f"Expected 'scanned:' stats in discover output:\n{output}"


def test_web_fetch_tool() -> None:
    """web_fetch tool: fetch example.com and verify success or tool-level failure output."""
    url = "https://example.com/"
    with tmux_session() as s:
        output = send_and_wait_for_completion(
            s,
            f"You MUST call the web_fetch tool. Fetch {url}. Do not answer until the tool runs.",
            description="web_fetch result or connection error",
            pane_predicate=lambda pane: f"url: {url}" in pane
            and ("example domain" in pane.lower() or f"failed to connect to {url}" in pane.lower()),
        )
        assert f"url: {url}" in output, f"Expected web_fetch params for {url}:\n{output}"
        assert (
            "example domain" in output.lower() or f"failed to connect to {url}" in output.lower()
        ), f"Expected fetched content or connection error for {url}:\n{output}"


def test_loaded_skill_is_used_via_absolute_referenced_path(tmp_path: Path) -> None:
    """Load a local skill in tmux, then verify the agent uses its referenced file."""
    skill_name = "tmux-e2e-skill"
    skill_description = "TMUX system test skill"
    token = f"TMUX_SKILL_TOKEN_{uuid.uuid4().hex[:8]}"
    skill_dir = tmp_path / ".claude" / "skills" / skill_name
    skill_dir.mkdir(parents=True)
    token_path = skill_dir / "token.txt"
    skill_path = skill_dir / "SKILL.md"

    token_path.write_text(token, encoding="utf-8")
    skill_path.write_text(
        "\n".join(
            [
                "---",
                f"name: {skill_name}",
                f"description: {skill_description}",
                "---",
                "",
                "# TMUX E2E Skill",
                "",
                "When the user asks for the tmux skill token, you must follow this workflow:",
                "1. Read [token.txt](token.txt).",
                "2. Reply with the exact token from that file.",
                '3. Include the sentence "This skill is loaded and being used."',
                "4. Do not guess if you have not read the file.",
            ]
        ),
        encoding="utf-8",
    )

    with tmux_session(working_directory=tmp_path) as s:
        load_output = send_and_wait_for_completion(
            s,
            f"/skills {skill_name}",
            description="skill load confirmation",
            pane_predicate=lambda pane: output_contains_all(
                pane,
                f"Loaded skill: {skill_name}",
                skill_description,
            ),
        )
        assert skill_description in load_output, (
            f"Expected skill description in load output:\n{load_output}"
        )

        final_output = send_and_wait_for_completion(
            s,
            "What is the tmux skill token? Use the loaded skill and do not guess.",
            description="skill token read and final response",
            pane_predicate=lambda pane: output_contains_in_order(
                pane,
                "token.txt",
                token,
                "This skill is loaded and being used.",
            ),
        )
        assert "token.txt" in final_output, f"Expected token file read in output:\n{final_output}"
        assert token in final_output, f"Expected token in output:\n{final_output}"
