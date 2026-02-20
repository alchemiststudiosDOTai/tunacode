"""Benchmark: discover tool -- speed, accuracy, and comparison vs legacy chain.

Generates synthetic repos of varying sizes, runs known queries against them,
and measures wall time + precision/recall against ground-truth expected files.

Usage:
    uv run python tests/benchmarks/bench_discover.py
"""

from __future__ import annotations

import random
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

from tunacode.tools.discover import _discover_sync

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SEED = 42
SMALL_FILES = 50
MEDIUM_FILES = 500
LARGE_FILES = 2000

LEGACY_PREVIEW_LINES = 200

# ---------------------------------------------------------------------------
# Content templates -- realistic Python files seeded with domain terms
# ---------------------------------------------------------------------------

_AUTH_TEMPLATE_A = dedent("""\
    from app.auth import jwt_handler

    class AuthService:
        \"\"\"Handles authentication and token validation.\"\"\"

        def validate_token(self, token: str) -> bool:
            return jwt_handler.verify(token)

        def login(self, username: str, password: str) -> str:
            session = create_session(username)
            return session.token
""")

_AUTH_TEMPLATE_B = dedent("""\
    from app.models import User

    def check_credentials(user: User, password: str) -> bool:
        \"\"\"Verify user credentials against stored hash.\"\"\"
        return verify_password(password, user.password_hash)

    def issue_jwt(user_id: int) -> str:
        return encode_jwt({"sub": user_id})
""")

_DB_TEMPLATE_A = dedent("""\
    from sqlalchemy import Column, Integer, String
    from app.db import Base

    class UserModel(Base):
        \"\"\"User database model with schema definition.\"\"\"
        __tablename__ = "users"
        id = Column(Integer, primary_key=True)
        name = Column(String(100))

    def run_migration():
        Base.metadata.create_all(engine)
""")

_DB_TEMPLATE_B = dedent("""\
    from app.db import session_factory

    class Repository:
        \"\"\"Generic database repository for query operations.\"\"\"
        def get_by_id(self, model_class, record_id: int):
            with session_factory() as session:
                return session.query(model_class).get(record_id)
""")

_API_TEMPLATE_A = dedent("""\
    from flask import Blueprint, request, jsonify

    api_bp = Blueprint("api", __name__)

    @api_bp.route("/users", methods=["GET"])
    def list_users():
        \"\"\"API endpoint for listing users.\"\"\"
        return jsonify(get_all_users())

    @api_bp.route("/users/<int:uid>", methods=["GET"])
    def get_user(uid: int):
        return jsonify(get_user_by_id(uid))
""")

_API_TEMPLATE_B = dedent("""\
    from app.middleware import require_auth

    class UserController:
        \"\"\"Controller handling user API requests and routing.\"\"\"
        @require_auth
        def handle_create(self, request):
            data = request.json
            return create_user(data)
""")

_ERROR_TEMPLATE_A = dedent("""\
    import logging

    class RetryError(Exception):
        \"\"\"Raised when all retry attempts are exhausted.\"\"\"
        pass

    def with_retry(fn, max_attempts: int = 3):
        \"\"\"Retry a function with exponential backoff on error.\"\"\"
        for attempt in range(max_attempts):
            try:
                return fn()
            except Exception as e:
                logging.warning("Attempt %d failed: %s", attempt + 1, e)
                if attempt == max_attempts - 1:
                    raise RetryError("All attempts failed") from e
""")

_ERROR_TEMPLATE_B = dedent("""\
    class ErrorHandler:
        \"\"\"Centralized error handling with fallback strategies.\"\"\"
        def handle_exception(self, exc: Exception) -> None:
            if isinstance(exc, ConnectionError):
                self.retry_connection()
            elif isinstance(exc, ValueError):
                self.log_validation_error(exc)
            else:
                raise
""")

_TOOL_TEMPLATE_A = dedent("""\
    from functools import wraps

    TOOL_REGISTRY: dict[str, callable] = {}

    def register_tool(name: str):
        \"\"\"Decorator to register a tool in the global registry.\"\"\"
        def decorator(fn):
            @wraps(fn)
            def wrapper(*args, **kwargs):
                return fn(*args, **kwargs)
            TOOL_REGISTRY[name] = wrapper
            return wrapper
        return decorator

    @register_tool("bash")
    def bash_tool(command: str) -> str:
        \"\"\"Execute a bash command.\"\"\"
        pass
""")

_TOOL_TEMPLATE_B = dedent("""\
    from app.tools.registry import TOOL_REGISTRY

    class ToolExecutor:
        \"\"\"Executes registered tools by name.\"\"\"
        def execute(self, tool_name: str, **kwargs):
            if tool_name not in TOOL_REGISTRY:
                raise KeyError(f"Unknown tool: {tool_name}")
            return TOOL_REGISTRY[tool_name](**kwargs)
""")

_NOISE_A = dedent("""\
    import math

    def compute_fibonacci(n: int) -> int:
        \"\"\"Compute nth Fibonacci number.\"\"\"
        if n <= 1:
            return n
        a, b = 0, 1
        for _ in range(2, n + 1):
            a, b = b, a + b
        return b
""")

_NOISE_B = dedent("""\
    import os
    import sys

    def format_bytes(size: int) -> str:
        \"\"\"Format byte count as human-readable string.\"\"\"
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"
""")

_NOISE_C = dedent("""\
    class StringUtils:
        @staticmethod
        def snake_to_camel(s: str) -> str:
            parts = s.split("_")
            return parts[0] + "".join(
                p.capitalize() for p in parts[1:]
            )

        @staticmethod
        def truncate(s: str, length: int = 80) -> str:
            if len(s) > length:
                return s[:length] + "..."
            return s
""")

DOMAIN_TEMPLATES: dict[str, list[str]] = {
    "auth": [_AUTH_TEMPLATE_A, _AUTH_TEMPLATE_B],
    "database": [_DB_TEMPLATE_A, _DB_TEMPLATE_B],
    "api": [_API_TEMPLATE_A, _API_TEMPLATE_B],
    "error": [_ERROR_TEMPLATE_A, _ERROR_TEMPLATE_B],
    "tool": [_TOOL_TEMPLATE_A, _TOOL_TEMPLATE_B],
}

NOISE_TEMPLATES = [_NOISE_A, _NOISE_B, _NOISE_C]

DOMAIN_DIRS: dict[str, list[str]] = {
    "auth": ["auth", "security", "session"],
    "database": ["db", "models", "migrations"],
    "api": ["api", "routes", "controllers"],
    "error": ["errors", "exceptions", "retry"],
    "tool": ["tools", "commands", "executors"],
}

NOISE_DIRS = [
    "utils", "helpers", "lib", "common",
    "internal", "support", "misc",
]


# ---------------------------------------------------------------------------
# Ground-truth queries
# ---------------------------------------------------------------------------

@dataclass
class BenchQuery:
    label: str
    query: str
    expected_domains: list[str]


QUERIES = [
    BenchQuery(
        "auth + token",
        "authentication and token validation",
        ["auth"],
    ),
    BenchQuery(
        "db + schema",
        "database models and schema",
        ["database"],
    ),
    BenchQuery(
        "error + retry",
        "error handling and retry",
        ["error"],
    ),
    BenchQuery(
        "api + routing",
        "API endpoints and routing",
        ["api"],
    ),
    BenchQuery(
        "tool registration",
        "tool registration",
        ["tool"],
    ),
]


# ---------------------------------------------------------------------------
# Synthetic repo generation
# ---------------------------------------------------------------------------

def _generate_repo(
    root: Path,
    file_count: int,
    rng: random.Random,
) -> dict[str, set[str]]:
    """Generate a synthetic repo.

    Returns {domain: set(relative_paths)} for ground truth.
    """
    domains = list(DOMAIN_TEMPLATES.keys())
    ground_truth: dict[str, set[str]] = {d: set() for d in domains}

    domain_count = int(file_count * 0.6)
    noise_count = file_count - domain_count
    files_per_domain = domain_count // len(domains)

    for domain in domains:
        dirs = DOMAIN_DIRS[domain]
        templates = DOMAIN_TEMPLATES[domain]
        for i in range(files_per_domain):
            dir_name = rng.choice(dirs)
            dir_path = root / "src" / dir_name
            dir_path.mkdir(parents=True, exist_ok=True)
            filename = f"{domain}_{i:03d}.py"
            filepath = dir_path / filename
            filepath.write_text(rng.choice(templates))
            rel = str(filepath.relative_to(root))
            ground_truth[domain].add(rel)

    for i in range(noise_count):
        dir_name = rng.choice(NOISE_DIRS)
        dir_path = root / "src" / dir_name
        dir_path.mkdir(parents=True, exist_ok=True)
        filename = f"util_{i:03d}.py"
        filepath = dir_path / filename
        filepath.write_text(rng.choice(NOISE_TEMPLATES))

    return ground_truth


# ---------------------------------------------------------------------------
# Legacy chain -- simulates old glob -> grep -> read workflow
# ---------------------------------------------------------------------------

LEGACY_SEARCH_TERMS: dict[str, list[str]] = {
    "authentication and token validation": [
        "auth", "token", "jwt", "login", "credential",
    ],
    "database models and schema": [
        "database", "model", "schema", "migration", "orm",
    ],
    "error handling and retry": [
        "error", "exception", "retry", "fallback",
    ],
    "API endpoints and routing": [
        "api", "route", "endpoint", "controller", "handler",
    ],
    "tool registration": [
        "tool", "register", "registry", "decorator",
    ],
}


def _legacy_chain(query: str, root: Path) -> list[str]:
    """Simulate old glob -> grep -> read chain."""
    terms = LEGACY_SEARCH_TERMS.get(query, query.lower().split())

    # Step 1: glob -- find files whose paths match terms
    candidates: list[Path] = []
    for path in root.rglob("*.py"):
        path_lower = str(path).lower()
        if any(t in path_lower for t in terms):
            candidates.append(path)

    # Step 2: grep -- search content for term matches
    matches: list[str] = []
    for path in candidates:
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        lines = text.splitlines()[:LEGACY_PREVIEW_LINES]
        preview_lower = "\n".join(lines).lower()
        hits = sum(1 for t in terms if t in preview_lower)
        if hits >= 2:
            matches.append(str(path.relative_to(root)))

    return matches


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

@dataclass
class BenchResult:
    query_label: str
    discover_ms: float
    legacy_ms: float
    precision: float
    recall: float
    f1: float
    discover_files: int
    legacy_files: int


def _compute_metrics(
    found: set[str],
    expected: set[str],
) -> tuple[float, float, float]:
    """Compute precision, recall, F1."""
    if not found:
        return (0.0, 0.0, 0.0)
    true_positives = len(found & expected)
    precision = true_positives / len(found) if found else 0.0
    recall = true_positives / len(expected) if expected else 0.0
    denom = precision + recall
    f1 = (2 * precision * recall / denom) if denom > 0 else 0.0
    return precision, recall, f1


# ---------------------------------------------------------------------------
# Run benchmark
# ---------------------------------------------------------------------------

def _run_benchmark(
    repo_label: str,
    file_count: int,
    rng: random.Random,
) -> list[BenchResult]:
    results: list[BenchResult] = []

    with tempfile.TemporaryDirectory(
        prefix=f"bench_{repo_label}_",
    ) as tmpdir:
        root = Path(tmpdir)
        ground_truth = _generate_repo(root, file_count, rng)

        for q in QUERIES:
            expected: set[str] = set()
            for domain in q.expected_domains:
                expected |= ground_truth[domain]

            # --- Discover ---
            t0 = time.perf_counter()
            report = _discover_sync(q.query, str(root))
            discover_ms = (time.perf_counter() - t0) * 1000

            discover_paths: set[str] = set()
            for cluster in report.clusters:
                for f in cluster.files:
                    try:
                        rel = str(Path(f.path).relative_to(root))
                    except ValueError:
                        rel = f.path
                    discover_paths.add(rel)

            # --- Legacy chain ---
            t0 = time.perf_counter()
            legacy_list = _legacy_chain(q.query, root)
            legacy_ms = (time.perf_counter() - t0) * 1000

            # --- Metrics (for discover) ---
            precision, recall, f1 = _compute_metrics(
                discover_paths, expected,
            )

            results.append(BenchResult(
                query_label=q.label,
                discover_ms=discover_ms,
                legacy_ms=legacy_ms,
                precision=precision,
                recall=recall,
                f1=f1,
                discover_files=len(discover_paths),
                legacy_files=len(legacy_list),
            ))

    return results


# ---------------------------------------------------------------------------
# Table output
# ---------------------------------------------------------------------------

COL_QUERY = 28
COL_NUM = 10
COL_METRIC = 7

HEADER = (
    f"{'Query':<{COL_QUERY}} "
    f"{'Discover':>{COL_NUM}} "
    f"{'Legacy':>{COL_NUM}} "
    f"{'Prec':>{COL_METRIC}} "
    f"{'Recall':>{COL_METRIC}} "
    f"{'F1':>{COL_METRIC}} "
    f"{'D-files':>{COL_METRIC}} "
    f"{'L-files':>{COL_METRIC}}"
)

SEP = "-" * len(HEADER)


def _format_row(r: BenchResult) -> str:
    return (
        f"{r.query_label:<{COL_QUERY}} "
        f"{r.discover_ms:>{COL_NUM}.1f} "
        f"{r.legacy_ms:>{COL_NUM}.1f} "
        f"{r.precision:>{COL_METRIC}.2f} "
        f"{r.recall:>{COL_METRIC}.2f} "
        f"{r.f1:>{COL_METRIC}.2f} "
        f"{r.discover_files:>{COL_METRIC}} "
        f"{r.legacy_files:>{COL_METRIC}}"
    )


def main() -> None:
    tiers = [
        ("small", SMALL_FILES),
        ("medium", MEDIUM_FILES),
        ("large", LARGE_FILES),
    ]

    print("=" * len(HEADER))
    print("Discover Tool Benchmark -- Speed + Accuracy + Comparison")
    print("=" * len(HEADER))
    print(
        "Times in ms. Prec/Recall/F1 measured for "
        "discover against ground truth.\n"
    )

    for label, count in tiers:
        print(f"--- {label} ({count} files) ---")
        print(HEADER)
        print(SEP)

        results = _run_benchmark(label, count, random.Random(SEED))

        for r in results:
            print(_format_row(r))

        avg_discover = sum(r.discover_ms for r in results) / len(results)
        avg_legacy = sum(r.legacy_ms for r in results) / len(results)
        avg_f1 = sum(r.f1 for r in results) / len(results)
        speedup = (
            avg_legacy / avg_discover
            if avg_discover > 0
            else float("inf")
        )

        print(SEP)
        print(
            f"{'AVG':<{COL_QUERY}} "
            f"{avg_discover:>{COL_NUM}.1f} "
            f"{avg_legacy:>{COL_NUM}.1f} "
            f"{'':>{COL_METRIC}} "
            f"{'':>{COL_METRIC}} "
            f"{avg_f1:>{COL_METRIC}.2f}"
        )
        print(f"  Speedup: {speedup:.1f}x\n")


if __name__ == "__main__":
    main()
