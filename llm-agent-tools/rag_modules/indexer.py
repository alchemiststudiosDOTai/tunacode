#!/usr/bin/env python3
"""
SQLite FTS5 Indexer for Claude Knowledge Base
Uses only Python stdlib - no external dependencies
"""

import argparse
import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple


class FlexibleIndexer:
    """Indexer for flexible directory structures using SQLite FTS5"""

    def __init__(self, directories: List[str], db_path: str):
        self.directories = [Path(d) for d in directories]
        self.db_path = Path(db_path)
        self.conn = None
        self.cursor = None

    def connect(self):
        """Connect to SQLite database"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.cursor = self.conn.cursor()

    def disconnect(self):
        """Disconnect from database"""
        if self.conn:
            self.conn.close()
            self.conn = None
            self.cursor = None

    def init_schema(self):
        """Initialize database schema with FTS5"""
        # Main documents table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS docs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                category TEXT NOT NULL,
                title TEXT,
                content TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_modified TIMESTAMP
            )
        """)

        # FTS5 virtual table for full-text search
        self.cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(
                title,
                content,
                category,
                content=docs,
                content_rowid=id
            )
        """)

        # Triggers to keep FTS index in sync
        self.cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS docs_ai AFTER INSERT ON docs BEGIN
                INSERT INTO docs_fts(rowid, title, content, category)
                VALUES (new.id, new.title, new.content, new.category);
            END
        """)

        self.cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS docs_ad AFTER DELETE ON docs BEGIN
                DELETE FROM docs_fts WHERE rowid = old.id;
            END
        """)

        self.cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS docs_au AFTER UPDATE ON docs BEGIN
                DELETE FROM docs_fts WHERE rowid = old.id;
                INSERT INTO docs_fts(rowid, title, content, category)
                VALUES (new.id, new.title, new.content, new.category);
            END
        """)

        # Index for faster lookups
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_docs_path ON docs(path)
        """)

        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_docs_category ON docs(category)
        """)

        self.conn.commit()

    def compute_file_hash(self, filepath: Path) -> str:
        """Compute SHA256 hash of file content"""
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def extract_title(self, content: str, filepath: Path) -> str:
        """Extract title from markdown content or use filename"""
        lines = content.split("\n")
        for line in lines[:10]:  # Check first 10 lines
            if line.startswith("# "):
                return line[2:].strip()
        # Fallback to filename without extension
        return filepath.stem.replace("_", " ").replace("-", " ").title()

    def should_index_file(self, filepath: Path) -> bool:
        """Check if file should be indexed"""
        # Index markdown, text, and JSON files
        return filepath.suffix in [".md", ".txt", ".markdown", ".json"]

    def get_existing_file_hash(self, filepath: str) -> Optional[str]:
        """Get hash of existing indexed file"""
        self.cursor.execute("SELECT file_hash FROM docs WHERE path = ?", (filepath,))
        result = self.cursor.fetchone()
        return result[0] if result else None

    def index_file(self, filepath: Path, category: str, root_dir: Path, force: bool = False):
        """Index a single file"""
        if not self.should_index_file(filepath):
            return False

        rel_path = str(filepath.relative_to(root_dir))
        file_hash = self.compute_file_hash(filepath)

        # Check if file needs updating
        existing_hash = self.get_existing_file_hash(rel_path)
        if existing_hash == file_hash and not force:
            return False  # File unchanged

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            title = self.extract_title(content, filepath)
            file_modified = datetime.fromtimestamp(filepath.stat().st_mtime)

            if existing_hash:
                # Update existing document with explicit timestamp to ensure it's different
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                self.cursor.execute(
                    """
                    UPDATE docs
                    SET content = ?, title = ?, file_hash = ?,
                        indexed_at = ?, file_modified = ?
                    WHERE path = ?
                """,
                    (content, title, file_hash, timestamp, file_modified, rel_path),
                )
            else:
                # Insert new document (will use default CURRENT_TIMESTAMP)
                self.cursor.execute(
                    """
                    INSERT INTO docs (path, category, title, content, file_hash, file_modified)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (rel_path, category, title, content, file_hash, file_modified),
                )

            # Commit the transaction to ensure the timestamp is updated in the database
            self.conn.commit()

            return True

        except Exception as e:
            print(f"Error indexing {filepath}: {e}")
            return False

    def index_directory(self, directory: Path) -> Tuple[int, int]:
        """Index all files in a directory and its subdirectories"""
        if not directory.exists():
            return 0, 0

        indexed = 0
        updated = 0

        # Process files directly in the root directory
        for filepath in directory.rglob("*"):
            if filepath.is_file():
                # Determine category from the directory structure
                # The category is the name of the immediate parent directory
                category = filepath.parent.name

                # Normalize category name
                category = category.replace(" ", "_").replace("-", "_")
                category = category.lower()

                if self.index_file(filepath, category, directory):
                    indexed += 1

        return indexed, updated

    def clean_deleted_files(self):
        """Remove entries for files that no longer exist"""
        self.cursor.execute("SELECT id, path FROM docs")
        all_docs = self.cursor.fetchall()

        deleted = 0
        for doc_id, path in all_docs:
            # Check if file exists in any of the provided directories
            file_exists = False
            for directory in self.directories:
                full_path = directory / path
                if full_path.exists():
                    file_exists = True
                    break

            if not file_exists:
                self.cursor.execute("DELETE FROM docs WHERE id = ?", (doc_id,))
                deleted += 1

        return deleted

    def build_index(self, incremental: bool = True):
        """Build or update the search index"""
        self.connect()
        self.init_schema()

        total_indexed = 0
        total_updated = 0

        print(f"Indexing directories: {', '.join(str(d) for d in self.directories)}")
        print("-" * 50)

        # Process each directory
        for directory in self.directories:
            indexed, updated = self.index_directory(directory)
            total_indexed += indexed
            total_updated += updated

        # Clean up deleted files
        if incremental:
            deleted = self.clean_deleted_files()
            if deleted > 0:
                print(f"  Cleaned up {deleted} deleted files")

        self.conn.commit()

        # Get statistics
        self.cursor.execute("SELECT COUNT(*) FROM docs")
        total_docs = self.cursor.fetchone()[0]

        print("-" * 50)
        print(f"Total documents in index: {total_docs}")
        print(f"Files indexed/updated: {total_indexed}")

        # Optimize FTS index
        self.cursor.execute("INSERT INTO docs_fts(docs_fts) VALUES('optimize')")
        self.conn.commit()

        self.disconnect()


def find_default_directories() -> List[str]:
    """Find default documentation directories in current directory or parent directory"""
    current_dir = Path.cwd()
    default_dirs = []

    # First check current directory
    # Check for docs directory first
    docs_dir = current_dir / "docs"
    if docs_dir.exists() and docs_dir.is_dir():
        default_dirs.append(str(docs_dir))

    # Check for documentation directory
    documentation_dir = current_dir / "documentation"
    if documentation_dir.exists() and documentation_dir.is_dir():
        default_dirs.append(str(documentation_dir))

    # If no documentation found in current directory, check parent directory
    if not default_dirs:
        parent_dir = current_dir.parent

        # Check for docs directory in parent
        docs_dir = parent_dir / "docs"
        if docs_dir.exists() and docs_dir.is_dir():
            default_dirs.append(str(docs_dir))

        # Check for documentation directory in parent
        documentation_dir = parent_dir / "documentation"
        if documentation_dir.exists() and documentation_dir.is_dir():
            default_dirs.append(str(documentation_dir))

    return default_dirs


def main():
    parser = argparse.ArgumentParser(
        description="Index documentation directories using SQLite FTS5"
    )
    parser.add_argument("--directories", nargs="*", help="Paths to directories to index")
    parser.add_argument("--db-path", required=True, help="Path to SQLite database")
    parser.add_argument(
        "--incremental", action="store_true", help="Incremental update (default)", default=True
    )
    parser.add_argument("--full", action="store_true", help="Full rebuild of index")

    args = parser.parse_args()

    # If no directories provided, use default behavior
    if not args.directories:
        args.directories = find_default_directories()
        if not args.directories:
            print("Error: No directories specified and no default directories found")
            print(
                "Default directories searched: docs/, documentation/ in current and parent directory"
            )
            return 1

    incremental = not args.full

    indexer = FlexibleIndexer(args.directories, args.db_path)
    indexer.build_index(incremental=incremental)


if __name__ == "__main__":
    main()
