#!/bin/bash

# RAG CLI - Retrieval-Augmented Generation Tools
# Usage: ./rag-cli.sh <command> [options]

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$SCRIPT_DIR/../.claude"
DEFAULT_DB="$SCRIPT_DIR/rag_knowledge.db"

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not installed"
    exit 1
fi

# Function to show usage
show_usage() {
    cat << EOF
RAG CLI - Retrieval-Augmented Generation Tools

Usage: $0 <command> [options]

Commands:
  index       Index documentation (defaults to memory-bank)
  search      Search indexed documentation
  stats       Show index statistics
  help        Show this help message

Index Command:
  $0 index [options]
    Options:
      --full           Full rebuild of index
      --dir DIR        Directory to index (default: $CLAUDE_DIR)
      --db PATH        Custom database path (default: $DEFAULT_DB)

Search Command:
  $0 search <query> [options]
    Options:
      --category CAT   Search within specific category
      --format FMT     Output format: json|text|markdown (default: json)
      --limit N        Maximum results (default: 10)
      --db PATH        Custom database path

Stats Command:
  $0 stats [options]
    Options:
      --json           Output in JSON format
      --db PATH        Custom database path

Examples:
  $0 index                           # Index .claude directory
  $0 index --full                    # Full rebuild
  $0 index --dir ./docs              # Index different directory
  $0 search "RAG architecture"       # Search all docs
  $0 search "design patterns" --category research --format markdown
  $0 stats                           # Show statistics

Environment:
  RAG_DB_PATH    Custom database path
  RAG_VERBOSE    Enable verbose output
EOF
}

# Function to run a RAG module
run_rag_module() {
    local module="$1"
    shift

    if [ -n "$RAG_VERBOSE" ]; then
        echo "Running: python3 $module $*" >&2
    fi

    python3 "$SCRIPT_DIR/$module" "$@"
}

# Parse command
case "${1:-help}" in
    index)
        shift
        FULL_REBUILD=""
        INDEX_DIR="$CLAUDE_DIR"
        DB_PATH="${RAG_DB_PATH:-$DEFAULT_DB}"

        # Parse options
        while [[ $# -gt 0 ]]; do
            case $1 in
                --full)
                    FULL_REBUILD="--full"
                    shift
                    ;;
                --dir)
                    INDEX_DIR="$2"
                    shift 2
                    ;;
                --db)
                    DB_PATH="$2"
                    shift 2
                    ;;
                *)
                    echo "Unknown option: $1" >&2
                    exit 1
                    ;;
            esac
        done

        # Check if directory exists
        if [ ! -d "$INDEX_DIR" ]; then
            echo "Error: Directory not found: $INDEX_DIR" >&2
            exit 1
        fi

        # Run indexer
        run_rag_module indexer.py \
            --directories "$INDEX_DIR" \
            --db-path "$DB_PATH" \
            $FULL_REBUILD
        ;;

    search)
        shift
        if [ -z "$1" ]; then
            echo "Error: search query is required" >&2
            exit 1
        fi

        QUERY="$1"
        shift
        CATEGORY=""
        FORMAT="json"
        LIMIT="10"
        DB_PATH="${RAG_DB_PATH:-$DEFAULT_DB}"

        # Parse options
        while [[ $# -gt 0 ]]; do
            case $1 in
                --category)
                    CATEGORY="$2"
                    shift 2
                    ;;
                --format)
                    FORMAT="$2"
                    shift 2
                    ;;
                --limit)
                    LIMIT="$2"
                    shift 2
                    ;;
                --db)
                    DB_PATH="$2"
                    shift 2
                    ;;
                *)
                    echo "Unknown option: $1" >&2
                    exit 1
                    ;;
            esac
        done

        # Run search
        run_rag_module search.py \
            --query "$QUERY" \
            --db-path "$DB_PATH" \
            --format "$FORMAT" \
            --limit "$LIMIT" \
            ${CATEGORY:+--category "$CATEGORY"}
        ;;

    stats)
        shift
        JSON_OUTPUT=""
        DB_PATH="${RAG_DB_PATH:-$DEFAULT_DB}"

        # Parse options
        while [[ $# -gt 0 ]]; do
            case $1 in
                --json)
                    JSON_OUTPUT="--json"
                    shift
                    ;;
                --db)
                    DB_PATH="$2"
                    shift 2
                    ;;
                *)
                    echo "Unknown option: $1" >&2
                    exit 1
                    ;;
            esac
        done

        # Run stats
        run_rag_module stats.py \
            --db-path "$DB_PATH" \
            $JSON_OUTPUT
        ;;

    help|--help|-h)
        show_usage
        ;;

    *)
        echo "Error: Unknown command '$1'" >&2
        echo
        show_usage
        exit 1
        ;;
esac