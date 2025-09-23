#!/usr/bin/env python3
"""
Statistics module for Claude Knowledge Base
Shows index statistics and metadata
"""

import argparse
import sqlite3
from pathlib import Path


class FlexibleStats:
    """Statistics for flexible directory structures using SQLite FTS5"""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.conn = None
        self.cursor = None

    def connect(self):
        """Connect to SQLite database"""
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

    def disconnect(self):
        """Disconnect from database"""
        if self.conn:
            self.conn.close()
            self.conn = None
            self.cursor = None

    def get_stats(self):
        """Get comprehensive statistics"""
        self.connect()

        stats = {}

        # Total documents
        self.cursor.execute("SELECT COUNT(*) as count FROM docs")
        stats["total_docs"] = self.cursor.fetchone()["count"]

        # Documents by category
        self.cursor.execute("""
            SELECT category, COUNT(*) as count 
            FROM docs 
            GROUP BY category 
            ORDER BY count DESC
        """)
        stats["by_category"] = {row["category"]: row["count"] for row in self.cursor.fetchall()}

        # Database size
        self.cursor.execute(
            "SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()"
        )
        stats["db_size"] = self.cursor.fetchone()["size"]

        # Recent updates
        self.cursor.execute("""
            SELECT path, indexed_at 
            FROM docs 
            ORDER BY indexed_at DESC 
            LIMIT 5
        """)
        stats["recent_updates"] = [
            (row["path"], row["indexed_at"]) for row in self.cursor.fetchall()
        ]

        # Index health - check for orphaned FTS entries
        self.cursor.execute("""
            SELECT COUNT(*) as orphaned
            FROM docs_fts 
            WHERE rowid NOT IN (SELECT id FROM docs)
        """)
        stats["orphaned_fts"] = self.cursor.fetchone()["orphaned"]

        # Average document size
        self.cursor.execute("SELECT AVG(LENGTH(content)) as avg_size FROM docs")
        stats["avg_doc_size"] = int(self.cursor.fetchone()["avg_size"] or 0)

        # Last index time
        self.cursor.execute("SELECT MAX(indexed_at) as last_indexed FROM docs")
        stats["last_indexed"] = self.cursor.fetchone()["last_indexed"]

        self.disconnect()
        return stats

    def format_stats(self, stats):
        """Format statistics for display"""
        output = []
        output.append("=" * 60)
        output.append("Documentation Knowledge Base Statistics")
        output.append("=" * 60)

        output.append(f"\nTotal Documents: {stats['total_docs']}")
        output.append(f"Database Size: {self.format_size(stats['db_size'])}")
        output.append(f"Average Document Size: {self.format_size(stats['avg_doc_size'])}")

        if stats["last_indexed"]:
            output.append(f"Last Indexed: {stats['last_indexed']}")

        output.append("\nDocuments by Category:")
        output.append("-" * 30)
        for category, count in stats["by_category"].items():
            output.append(f"  {category:20} : {count:4} docs")

        if stats["recent_updates"]:
            output.append("\nRecent Updates:")
            output.append("-" * 30)
            for path, timestamp in stats["recent_updates"]:
                output.append(f"  {timestamp} - {path}")

        if stats["orphaned_fts"] > 0:
            output.append(f"\n⚠ Warning: {stats['orphaned_fts']} orphaned FTS entries found")
            output.append("  Run index rebuild to fix")

        output.append("\n" + "=" * 60)
        return "\n".join(output)

    def format_size(self, bytes):
        """Format byte size to human readable"""
        for unit in ["B", "KB", "MB", "GB"]:
            if bytes < 1024.0:
                return f"{bytes:.1f} {unit}"
            bytes /= 1024.0
        return f"{bytes:.1f} TB"


def main():
    parser = argparse.ArgumentParser(description="Show documentation index statistics")
    parser.add_argument("--db-path", required=True, help="Path to SQLite database")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    stats_tool = FlexibleStats(args.db_path)
    stats = stats_tool.get_stats()

    if args.json:
        import json

        print(json.dumps(stats, indent=2, default=str))
    else:
        print(stats_tool.format_stats(stats))


if __name__ == "__main__":
    main()
