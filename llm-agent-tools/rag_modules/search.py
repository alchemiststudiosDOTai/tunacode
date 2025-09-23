#!/usr/bin/env python3
"""
SQLite FTS5 Search for Claude Knowledge Base
Compact output formats for agent consumption
"""

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List


class FlexibleSearcher:
    """Search interface for flexible directory structures using SQLite FTS5"""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.conn = None
        self.cursor = None

    def connect(self):
        """Connect to SQLite database"""
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row  # Enable column access by name
        self.cursor = self.conn.cursor()
        # Ensure connection is not None
        if self.conn is None:
            raise RuntimeError("Failed to establish database connection")

    def disconnect(self):
        """Disconnect from database"""
        if self.conn is not None:
            self.conn.close()
            self.conn = None
            self.cursor = None

    def extract_snippet(self, content: str, query: str, max_length: int = 500) -> str:
        """Extract relevant snippet around search term"""
        content_lower = content.lower()
        query_lower = query.lower()

        # Find first occurrence of query
        pos = content_lower.find(query_lower)
        if pos == -1:
            # If exact match not found, return beginning
            return content[:max_length].strip() + ("..." if len(content) > max_length else "")

        # Calculate snippet boundaries
        start = max(0, pos - max_length // 3)
        end = min(len(content), pos + len(query) + (2 * max_length // 3))

        snippet = content[start:end].strip()

        # Add ellipsis if truncated
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."

        return snippet

    def highlight_text(self, text: str, query: str, format: str = "text") -> str:
        """Highlight search terms in text"""
        if format == "markdown":
            # Use bold for markdown
            for term in query.split():
                import re

                pattern = re.compile(re.escape(term), re.IGNORECASE)
                text = pattern.sub(lambda m: f"**{m.group()}**", text)
        elif format == "text":
            # Use uppercase for plain text
            for term in query.split():
                import re

                pattern = re.compile(re.escape(term), re.IGNORECASE)
                text = pattern.sub(lambda m: m.group().upper(), text)
        return text

    def search(self, query: str, limit: int = 10, max_snippet: int = 500) -> List[Dict[str, Any]]:
        """
        Search the FTS5 index
        Returns list of results with snippets
        """
        self.connect()

        # Use FTS5 MATCH for search
        sql = """
            SELECT 
                d.id,
                d.path,
                d.category,
                d.title,
                d.content,
                d.indexed_at,
                bm25(docs_fts) as rank
            FROM docs d
            JOIN docs_fts ON d.id = docs_fts.rowid
            WHERE docs_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """

        try:
            self.cursor.execute(sql, (query, limit))
            rows = self.cursor.fetchall()

            results = []
            for row in rows:
                snippet = self.extract_snippet(row["content"], query, max_snippet)
                results.append(
                    {
                        "path": row["path"],
                        "category": row["category"],
                        "title": row["title"],
                        "snippet": snippet,
                        "rank": row["rank"],
                    }
                )

            return results

        finally:
            self.disconnect()

    def format_results(
        self, results: List[Dict[str, Any]], query: str, format: str = "json"
    ) -> str:
        """Format search results for output"""
        if not results:
            if format == "json":
                return json.dumps({"results": [], "count": 0, "query": query})
            else:
                return "No results found."

        if format == "json":
            # Compact JSONL format for agent consumption
            output = []
            for r in results:
                output.append(
                    json.dumps(
                        {
                            "p": r["path"],  # path
                            "c": r["category"],  # category
                            "t": r["title"],  # title
                            "s": r["snippet"],  # snippet
                        },
                        ensure_ascii=False,
                    )
                )
            return "\n".join(output)

        elif format == "text":
            # Human-readable text format
            output = [f"Found {len(results)} results for '{query}':\n"]
            for i, r in enumerate(results, 1):
                snippet = self.highlight_text(r["snippet"], query, "text")
                output.append(f"{i}. [{r['category']}] {r['title']}")
                output.append(f"   Path: {r['path']}")
                output.append(f"   {snippet}\n")
            return "\n".join(output)

        elif format == "markdown":
            # Markdown format with highlights
            output = [f"## Search Results for: {query}", f"*Found {len(results)} matches*\n"]
            for i, r in enumerate(results, 1):
                snippet = self.highlight_text(r["snippet"], query, "markdown")
                output.append(f"### {i}. {r['title']}")
                output.append(f"**Category:** `{r['category']}` | **Path:** `{r['path']}`")
                output.append(f"\n{snippet}\n")
                output.append("---")
            return "\n".join(output)

        else:
            raise ValueError(f"Unknown format: {format}")

    def search_category(self, query: str, category: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search within a specific category"""
        self.connect()

        sql = """
            SELECT 
                d.id,
                d.path,
                d.category,
                d.title,
                d.content,
                d.indexed_at,
                bm25(docs_fts) as rank
            FROM docs d
            JOIN docs_fts ON d.id = docs_fts.rowid
            WHERE docs_fts MATCH ? AND d.category = ?
            ORDER BY rank
            LIMIT ?
        """

        try:
            self.cursor.execute(sql, (query, category, limit))
            rows = self.cursor.fetchall()

            results = []
            for row in rows:
                snippet = self.extract_snippet(row["content"], query, 500)
                results.append(
                    {
                        "path": row["path"],
                        "category": row["category"],
                        "title": row["title"],
                        "snippet": snippet,
                        "rank": row["rank"],
                    }
                )

            return results

        finally:
            self.disconnect()


def main():
    parser = argparse.ArgumentParser(description="Search documentation knowledge base")
    parser.add_argument("--db-path", required=True, help="Path to SQLite database")
    parser.add_argument("--query", required=True, help="Search query")
    parser.add_argument("--limit", type=int, default=10, help="Maximum results")
    parser.add_argument("--max-snippet", type=int, default=500, help="Maximum snippet length")
    parser.add_argument(
        "--format", choices=["json", "text", "markdown"], default="json", help="Output format"
    )
    parser.add_argument("--category", help="Search specific category only")

    args = parser.parse_args()

    searcher = FlexibleSearcher(args.db_path)

    if args.category:
        results = searcher.search_category(args.query, args.category, args.limit)
    else:
        results = searcher.search(args.query, args.limit, args.max_snippet)

    output = searcher.format_results(results, args.query, args.format)
    print(output)


if __name__ == "__main__":
    main()
