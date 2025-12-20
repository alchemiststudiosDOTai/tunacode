#!/usr/bin/env bash
set -euo pipefail

# exa-search - Exa API search tool for LLM agents
# https://docs.exa.ai/reference/search

readonly API_URL="https://api.exa.ai/search"
readonly VERSION="1.0.0"

# Defaults
num_results=10
search_type="auto"
category=""
include_domain=""
exclude_domain=""
include_text=false
include_highlights=false
include_summary=false
start_date=""
end_date=""
output_format="markdown"
verbose=false

usage() {
    cat >&2 <<EOF
exa-search v${VERSION} - Search the web via Exa API

USAGE:
    exa-search [OPTIONS] <query>

OPTIONS:
    -n, --num <N>         Number of results (default: 10, max: 100)
    -t, --type <TYPE>     Search type: auto, neural, fast, deep (default: auto)
    -c, --category <CAT>  Category: news, research, github, pdf, company, tweet
    -d, --domain <DOM>    Include only this domain
    -x, --exclude <DOM>   Exclude this domain
    --text                Include full page text
    --highlights          Include relevant snippets
    --summary             Include AI-generated summary
    --after <DATE>        Published after date (YYYY-MM-DD)
    --before <DATE>       Published before date (YYYY-MM-DD)
    -o, --output <FMT>    Output format: markdown, json (default: markdown)
    -v, --verbose         Enable verbose output
    -h, --help            Show this help

# ENVIRONMENT:
#    EXA_API_KEY           Required. Your Exa API key.
#                          Load it via 'source .env' (ensure it has 'export EXA_API_KEY=...')
#                          or pass it inline: 'EXA_API_KEY=... ./tools/exa-search.sh ...'

EXAMPLES:
    exa-search "rust async programming"
    exa-search -n 5 -t neural "latest AI news"
    exa-search --highlights -d docs.rs "tokio runtime"
    exa-search -c research --after 2024-01-01 "transformer architecture"
EOF
    exit 1
}

die() {
    echo "error: $*" >&2
    exit 1
}

log() {
    [[ "$verbose" == true ]] && echo "debug: $*" >&2
}

# Parse arguments
query=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        -n|--num)
            num_results="$2"
            shift 2
            ;;
        -t|--type)
            search_type="$2"
            shift 2
            ;;
        -c|--category)
            category="$2"
            shift 2
            ;;
        -d|--domain)
            include_domain="$2"
            shift 2
            ;;
        -x|--exclude)
            exclude_domain="$2"
            shift 2
            ;;
        --text)
            include_text=true
            shift
            ;;
        --highlights)
            include_highlights=true
            shift
            ;;
        --summary)
            include_summary=true
            shift
            ;;
        --after)
            start_date="$2"
            shift 2
            ;;
        --before)
            end_date="$2"
            shift 2
            ;;
        -o|--output)
            output_format="$2"
            shift 2
            ;;
        -v|--verbose)
            verbose=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        -*)
            die "unknown option: $1"
            ;;
        *)
            query="$1"
            shift
            ;;
    esac
done

# Validate
[[ -z "${EXA_API_KEY:-}" ]] && die "EXA_API_KEY environment variable not set"
[[ -z "$query" ]] && usage

# Build JSON payload
build_payload() {
    local payload
    payload=$(jq -n \
        --arg query "$query" \
        --arg type "$search_type" \
        --argjson num "$num_results" \
        '{query: $query, type: $type, numResults: $num}')

    [[ -n "$category" ]] && payload=$(echo "$payload" | jq --arg cat "$category" '. + {category: $cat}')
    [[ -n "$include_domain" ]] && payload=$(echo "$payload" | jq --arg dom "$include_domain" '. + {includeDomains: [$dom]}')
    [[ -n "$exclude_domain" ]] && payload=$(echo "$payload" | jq --arg dom "$exclude_domain" '. + {excludeDomains: [$dom]}')
    [[ -n "$start_date" ]] && payload=$(echo "$payload" | jq --arg date "$start_date" '. + {startPublishedDate: ($date + "T00:00:00.000Z")}')
    [[ -n "$end_date" ]] && payload=$(echo "$payload" | jq --arg date "$end_date" '. + {endPublishedDate: ($date + "T23:59:59.999Z")}')

    # Content options
    local contents="{}"
    if [[ "$include_text" == true ]]; then
        contents=$(echo "$contents" | jq '. + {text: true}')
    fi
    if [[ "$include_highlights" == true ]]; then
        contents=$(echo "$contents" | jq '. + {highlights: true}')
    fi
    if [[ "$include_summary" == true ]]; then
        contents=$(echo "$contents" | jq '. + {summary: true}')
    fi
    if [[ "$contents" != "{}" ]]; then
        payload=$(echo "$payload" | jq --argjson contents "$contents" '. + {contents: $contents}')
    fi

    echo "$payload"
}

# Make API request
request() {
    local payload="$1"
    curl -sS -X POST "$API_URL" \
        -H "Content-Type: application/json" \
        -H "x-api-key: $EXA_API_KEY" \
        -d "$payload"
}

# Format as markdown
format_markdown() {
    local response="$1"
    local query_display="$2"

    # Check for error
    if echo "$response" | jq -e '.error' >/dev/null 2>&1; then
        local err_msg
        err_msg=$(echo "$response" | jq -r '.error // "Unknown error"')
        die "API error: $err_msg"
    fi

    echo "# Search: \"$query_display\""
    echo ""

    local count
    count=$(echo "$response" | jq '.results | length')

    if [[ "$count" -eq 0 ]]; then
        echo "No results found."
        return
    fi

    echo "$response" | jq -r '
        .results | to_entries[] |
        "\(.key + 1). [\(.value.title // "Untitled")](\(.value.url))" +
        (if .value.publishedDate then "\n   Published: \(.value.publishedDate | split("T")[0])" else "" end) +
        (if .value.author then " | Author: \(.value.author)" else "" end) +
        (if .value.highlights then "\n   > " + (.value.highlights[0] // "" | gsub("\n"; " ")) else "" end) +
        (if .value.summary then "\n   " + (.value.summary | gsub("\n"; " ")) else "" end) +
        (if .value.text then "\n\n   ```\n   " + (.value.text[0:500] | gsub("\n"; "\n   ")) + "...\n   ```" else "" end) +
        "\n"
    '

    echo "---"
    local cost
    cost=$(echo "$response" | jq -r '.costDollars.total // "N/A"')
    echo "Results: $count | Cost: \$$cost"
}

# Main
main() {
    local payload response

    payload=$(build_payload)
    response=$(request "$payload")

    case "$output_format" in
        json)
            echo "$response" | jq .
            ;;
        markdown|*)
            format_markdown "$response" "$query"
            ;;
    esac
}

main