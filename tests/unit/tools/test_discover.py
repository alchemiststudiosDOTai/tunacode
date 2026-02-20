"""Tests for the discover tool — term extraction, scoring, clustering, and integration."""

from pathlib import Path

from tunacode.tools.discover import (
    MAX_REPORT_FILES,
    ConceptCluster,
    DiscoveryReport,
    FileEntry,
    Relevance,
    _build_excerpt,
    _build_relevant_tree,
    _cluster_prospects,
    _collect_candidates,
    _detect_dominant_extensions,
    _discover_sync,
    _empty_prospect,
    _evaluate_prospect,
    _extract_imports,
    _extract_search_terms,
    _extract_symbols,
    _generate_glob_patterns,
    _infer_role,
    _Prospect,
)

# ---------------------------------------------------------------------------
# Term extraction
# ---------------------------------------------------------------------------


class TestExtractSearchTerms:
    def test_extracts_snake_case_identifiers(self):
        terms = _extract_search_terms("find the validate_token function")
        assert "validate_token" in terms["exact"]

    def test_extracts_camel_case_identifiers(self):
        terms = _extract_search_terms("where is AuthService defined")
        assert "AuthService" in terms["exact"]

    def test_extracts_dotted_identifiers(self):
        terms = _extract_search_terms("look at auth.middleware module")
        assert "auth.middleware" in terms["exact"]

    def test_expands_known_concepts(self):
        terms = _extract_search_terms("where is auth handled")
        # "auth" should expand to include related terms
        assert "auth" in terms["filename"]
        assert "login" in terms["filename"]
        assert "token" in terms["filename"]

    def test_filters_noise_words(self):
        terms = _extract_search_terms("where are all the code files defined")
        assert "where" not in terms["filename"]
        assert "all" not in terms["filename"]
        assert "code" not in terms["filename"]
        assert "defined" not in terms["filename"]

    def test_unknown_terms_used_as_both(self):
        terms = _extract_search_terms("frobnicator logic")
        assert "frobnicator" in terms["filename"]
        assert "frobnicator" in terms["content"]

    def test_deduplicates_terms(self):
        terms = _extract_search_terms("auth auth auth login")
        filename_count = terms["filename"].count("auth")
        assert filename_count <= 1


# ---------------------------------------------------------------------------
# Glob pattern generation
# ---------------------------------------------------------------------------


class TestGenerateGlobPatterns:
    def test_generates_three_patterns_per_term(self):
        terms = {"filename": ["auth"], "exact": [], "content": []}
        patterns = _generate_glob_patterns(terms, extensions=[])
        assert "**/*auth*" in patterns
        assert "**/auth*/**" in patterns
        assert "**/*auth*/**" in patterns

    def test_generates_extension_specific_patterns(self):
        terms = {"filename": ["auth"], "exact": [], "content": []}
        patterns = _generate_glob_patterns(terms, extensions=[".py", ".ts"])
        assert "**/*auth*.py" in patterns
        assert "**/*auth*.ts" in patterns

    def test_deduplicates_patterns(self):
        terms = {"filename": ["auth", "auth"], "exact": [], "content": []}
        patterns = _generate_glob_patterns(terms, extensions=[])
        assert len(patterns) == len(set(patterns))


# ---------------------------------------------------------------------------
# Symbol extraction
# ---------------------------------------------------------------------------


class TestExtractSymbols:
    def test_extracts_python_def(self):
        text = "def validate_token(token: str) -> bool:"
        symbols = _extract_symbols(text)
        assert "validate_token" in symbols

    def test_extracts_python_class(self):
        text = "class AuthService:"
        symbols = _extract_symbols(text)
        assert "AuthService" in symbols

    def test_extracts_js_function(self):
        text = "function handleLogin(req, res) {"
        symbols = _extract_symbols(text)
        assert "handleLogin" in symbols

    def test_extracts_rust_fn(self):
        text = "pub fn validate_credentials(user: &User) -> Result<(), Error> {"
        symbols = _extract_symbols(text)
        assert "validate_credentials" in symbols

    def test_extracts_go_func(self):
        text = "func (s *Server) HandleAuth(w http.ResponseWriter, r *http.Request) {"
        symbols = _extract_symbols(text)
        assert "HandleAuth" in symbols

    def test_filters_python_keywords(self):
        text = "def for(x): pass\nclass None: pass"
        symbols = _extract_symbols(text)
        # "for" and "None" are keywords, should be filtered
        assert "for" not in symbols
        assert "None" not in symbols

    def test_filters_js_keywords(self):
        text = "function const() {}\nexport class default {}"
        symbols = _extract_symbols(text)
        assert "const" not in symbols
        assert "default" not in symbols

    def test_deduplicates(self):
        text = "def foo(): ...\ndef foo(): ..."
        symbols = _extract_symbols(text)
        assert symbols.count("foo") == 1


# ---------------------------------------------------------------------------
# Import extraction
# ---------------------------------------------------------------------------


class TestExtractImports:
    def test_python_from_import(self):
        text = "from tunacode.tools import bash"
        imports = _extract_imports(text)
        assert "tunacode.tools" in imports

    def test_python_import(self):
        text = "import asyncio"
        imports = _extract_imports(text)
        assert "asyncio" in imports

    def test_js_require(self):
        text = "const express = require('express')"
        imports = _extract_imports(text)
        assert "express" in imports

    def test_js_from_import(self):
        text = 'import { Router } from "express"'
        imports = _extract_imports(text)
        assert "express" in imports

    def test_deduplicates(self):
        text = "import os\nimport os"
        imports = _extract_imports(text)
        assert imports.count("os") == 1


# ---------------------------------------------------------------------------
# Prospect evaluation
# ---------------------------------------------------------------------------


class TestEvaluateProspect:
    def test_keeps_high_relevance_file(self, isolated_tmp_dir):
        f = isolated_tmp_dir / "auth.py"
        f.write_text(
            "def validate_token(token):\n"
            "    # auth token validation\n"
            "    return check_jwt(token)\n"
        )
        terms = {
            "exact": ["validate_token"],
            "filename": ["auth", "token"],
            "content": ["auth", "token", "jwt", "validate"],
        }
        prospect = _evaluate_prospect(f, terms)
        assert prospect.keep is True
        assert prospect.relevance == Relevance.HIGH

    def test_skips_irrelevant_file(self, isolated_tmp_dir):
        f = isolated_tmp_dir / "utils.py"
        f.write_text("def add(a, b):\n    return a + b\n")
        terms = {
            "exact": [],
            "filename": ["auth", "token"],
            "content": ["auth", "token", "jwt"],
        }
        prospect = _evaluate_prospect(f, terms)
        assert prospect.keep is False

    def test_handles_unreadable_file(self, isolated_tmp_dir):
        f = isolated_tmp_dir / "broken.py"
        f.write_text("content")
        f.chmod(0o000)
        terms = {"exact": [], "filename": [], "content": []}
        prospect = _evaluate_prospect(f, terms)
        assert prospect.keep is False
        # Restore permissions for cleanup
        f.chmod(0o644)

    def test_extracts_symbols_and_imports(self, isolated_tmp_dir):
        f = isolated_tmp_dir / "service.py"
        f.write_text(
            "from tunacode.core import agent\n"
            "import asyncio\n\n"
            "class ToolExecutor:\n"
            "    async def run_tool(self, name):\n"
            "        pass\n"
        )
        terms = {
            "exact": ["ToolExecutor"],
            "filename": ["tool"],
            "content": ["tool", "executor", "agent"],
        }
        prospect = _evaluate_prospect(f, terms)
        assert prospect.keep is True
        assert "ToolExecutor" in prospect.key_symbols
        assert "tunacode.core" in prospect.imports


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------


class TestClusterProspects:
    def _make_prospect(
        self,
        path: str,
        *,
        keep: bool = True,
        relevance: Relevance = Relevance.HIGH,
        score: float = 5.0,
    ) -> _Prospect:
        return _Prospect(
            path=Path(path), keep=keep, relevance=relevance,
            role="test", key_symbols=[], imports=[],
            excerpt="", line_count=10, score=score,
        )

    def test_groups_by_directory(self):
        prospects = [
            self._make_prospect("/src/auth/login.py"),
            self._make_prospect("/src/auth/token.py"),
            self._make_prospect("/src/db/models.py"),
        ]
        clusters, overflow = _cluster_prospects(prospects)
        cluster_names = {c.name for c in clusters}
        assert "auth" in cluster_names
        assert "db" in cluster_names
        assert not overflow

    def test_caps_at_max_report_files(self):
        # Create more than MAX_REPORT_FILES prospects across directories
        prospects = [
            self._make_prospect(f"/src/dir{i}/file{j}.py", score=float(30 - i))
            for i in range(5)
            for j in range(10)
        ]
        clusters, overflow = _cluster_prospects(prospects)
        total_files = sum(len(c.files) for c in clusters)
        assert total_files <= MAX_REPORT_FILES
        assert len(overflow) > 0

    def test_skips_non_kept_prospects(self):
        prospects = [
            self._make_prospect("/src/auth.py", keep=True),
            self._make_prospect("/src/utils.py", keep=False),
        ]
        clusters, _ = _cluster_prospects(prospects)
        all_paths = [f.path for c in clusters for f in c.files]
        assert "/src/utils.py" not in all_paths


# ---------------------------------------------------------------------------
# Relevant file tree
# ---------------------------------------------------------------------------


class TestBuildRelevantTree:
    def test_builds_tree_with_markers(self, isolated_tmp_dir):
        auth_dir = isolated_tmp_dir / "src" / "auth"
        auth_dir.mkdir(parents=True)
        login_file = auth_dir / "login.py"
        login_file.write_text("pass")

        prospects = [
            _Prospect(
                path=login_file, keep=True, relevance=Relevance.HIGH,
                role="test", key_symbols=[], imports=[],
                excerpt="", line_count=1, score=5.0,
            ),
        ]
        tree = _build_relevant_tree(prospects, isolated_tmp_dir)
        assert "src/" in tree
        assert "auth/" in tree
        assert "login.py" in tree


# ---------------------------------------------------------------------------
# Report serialization
# ---------------------------------------------------------------------------


class TestDiscoveryReport:
    def test_to_context_format(self):
        report = DiscoveryReport(
            query="where is auth",
            summary="Found 2 files (1 high, 1 medium) in 1 areas.",
            clusters=[
                ConceptCluster(
                    name="auth",
                    description="2 files (1 high relevance)",
                    files=[
                        FileEntry(
                            path="src/auth/login.py",
                            relevance=Relevance.HIGH,
                            role="auth/login (validate)",
                            key_symbols=["validate"],
                            imports_from=["tunacode.core"],
                            line_count=50,
                            excerpt="def validate(token): ...",
                        ),
                        FileEntry(
                            path="src/auth/token.py",
                            relevance=Relevance.MEDIUM,
                            role="auth/token",
                            key_symbols=[],
                            imports_from=[],
                            line_count=20,
                        ),
                    ],
                ),
            ],
            total_files_scanned=100,
            total_candidates=2,
        )
        ctx = report.to_context()
        assert "# Discovery: where is auth" in ctx
        assert "Found 2 files" in ctx
        assert "100 scanned" in ctx
        assert "src/auth/login.py" in ctx
        assert "defines: validate" in ctx
        assert "imports: tunacode.core" in ctx

    def test_overflow_dirs_shown(self):
        report = DiscoveryReport(
            query="test",
            summary="Found many files.",
            clusters=[],
            total_files_scanned=50,
            total_candidates=30,
            overflow_dirs=["utils (+5)", "helpers"],
        )
        ctx = report.to_context()
        assert "+2 more in:" in ctx
        assert "utils (+5)" in ctx


# ---------------------------------------------------------------------------
# Infer role
# ---------------------------------------------------------------------------


class TestInferRole:
    def test_with_symbols(self):
        role = _infer_role(Path("/src/auth/login.py"), ["validate", "check_jwt"])
        assert "auth/login" in role
        assert "validate" in role

    def test_without_symbols(self):
        role = _infer_role(Path("/src/auth/login.py"), [])
        assert role == "auth/login"

    def test_root_file(self):
        role = _infer_role(Path("setup.py"), [])
        # parent is "." so no parent prefix
        assert "setup" in role


# ---------------------------------------------------------------------------
# Build excerpt
# ---------------------------------------------------------------------------


class TestBuildExcerpt:
    def test_picks_relevant_lines(self):
        lines = [
            "import os",
            "",
            "def validate_token(token):",
            "    # check jwt auth",
            "    return True",
        ]
        terms = {"exact": ["validate_token"], "content": ["auth", "token", "jwt"]}
        excerpt = _build_excerpt(lines, terms)
        assert "validate_token" in excerpt

    def test_limits_to_max_lines(self):
        lines = [f"auth token line {i}" for i in range(20)]
        terms = {"exact": [], "content": ["auth", "token"]}
        excerpt = _build_excerpt(lines, terms, max_lines=2)
        # Should have at most 2 segments separated by " | "
        assert excerpt.count(" | ") <= 1


# ---------------------------------------------------------------------------
# Empty prospect
# ---------------------------------------------------------------------------


class TestEmptyProspect:
    def test_keep_is_false(self):
        p = _empty_prospect(Path("/foo.py"))
        assert p.keep is False
        assert p.key_symbols == []
        assert p.imports == []


# ---------------------------------------------------------------------------
# Integration: full pipeline on temp directory
# ---------------------------------------------------------------------------


class TestDiscoverSync:
    def test_finds_relevant_files(self, isolated_tmp_dir):
        # Set up a mini project
        tools_dir = isolated_tmp_dir / "src" / "tools"
        tools_dir.mkdir(parents=True)
        (tools_dir / "bash.py").write_text(
            "from tunacode.tools.decorators import base_tool\n\n"
            "@base_tool\n"
            "async def bash(command: str) -> str:\n"
            "    '''Execute a bash command.'''\n"
            "    pass\n"
        )
        (tools_dir / "grep.py").write_text(
            "from tunacode.tools.decorators import base_tool\n\n"
            "@base_tool\n"
            "async def grep(pattern: str) -> str:\n"
            "    '''Search for pattern in files.'''\n"
            "    pass\n"
        )
        (isolated_tmp_dir / "README.md").write_text("# My Project\nNothing about tools here.")

        report = _discover_sync("tool decorators and bash command", str(isolated_tmp_dir))
        assert report.total_candidates > 0
        # bash.py should be found (mentions "tool", "bash", "command", "decorators")
        all_paths = [f.path for c in report.clusters for f in c.files]
        bash_found = any("bash.py" in p for p in all_paths)
        assert bash_found, f"bash.py not found in {all_paths}"

    def test_returns_empty_for_no_matches(self, isolated_tmp_dir):
        (isolated_tmp_dir / "unrelated.py").write_text("x = 1")
        report = _discover_sync("quantum entanglement simulator", str(isolated_tmp_dir))
        assert report.total_candidates == 0


# ---------------------------------------------------------------------------
# Detect dominant extensions
# ---------------------------------------------------------------------------


class TestDetectDominantExtensions:
    def test_finds_python_files(self, isolated_tmp_dir):
        for i in range(5):
            (isolated_tmp_dir / f"file{i}.py").write_text(f"x = {i}")
        exts = _detect_dominant_extensions(isolated_tmp_dir)
        assert ".py" in exts

    def test_ignores_rare_extensions(self, isolated_tmp_dir):
        for i in range(5):
            (isolated_tmp_dir / f"file{i}.py").write_text(f"x = {i}")
        (isolated_tmp_dir / "one.lua").write_text("x = 1")
        exts = _detect_dominant_extensions(isolated_tmp_dir)
        assert ".lua" not in exts


# ---------------------------------------------------------------------------
# Collect candidates
# ---------------------------------------------------------------------------


class TestCollectCandidates:
    def test_filters_non_source_files(self, isolated_tmp_dir):
        (isolated_tmp_dir / "code.py").write_text("pass")
        (isolated_tmp_dir / "image.png").write_text("not an image")

        from tunacode.tools.ignore import IgnoreManager

        ignore = IgnoreManager(isolated_tmp_dir, patterns=(), exclude_dirs=frozenset())
        # Use a pattern that matches "code" — single-walk approach needs real terms
        candidates = _collect_candidates(["**/*code*"], isolated_tmp_dir, ignore)
        paths_str = [str(c) for c in candidates]
        assert any("code.py" in p for p in paths_str)
        assert not any("image.png" in p for p in paths_str)
