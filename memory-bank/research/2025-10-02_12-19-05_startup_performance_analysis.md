# Research – Startup Performance Analysis
**Date:** 2025-10-02
**Owner:** Claude Code
**Phase:** Research
**Last Updated:** 2025-10-02
**Last Updated By:** Claude Code
**Git Commit:** 83e26ccdd454095063c09dd04e3b6b3241aea278
**Tags:** [startup, performance, bottlenecks, optimization]

## Goal
Identify and analyze all factors contributing to slow startup times in the TunaCode CLI application.

## Additional Search
- `grep -ri "startup\|init\|bootstrap" .claude/`

## Findings

### Primary Entry Points & Startup Sequence
- **Main CLI entry**: `src/tunacode/cli/main.py` - Primary startup point with Typer CLI framework
- **Package initialization**: `src/tunacode/__init__.py:2-4` - Triggers logging setup immediately on import
- **Configuration loading**: `src/tunacode/core/setup/config_setup.py:50` - Synchronous config loading blocks startup
- **REPL startup**: `src/tunacode/cli/repl.py:345-350` - Background CodeIndex pre-warming

### Critical Performance Bottlenecks

#### 1. **Heavy UI Framework Imports** (`src/tunacode/ui/console.py:6-13`)
- **Issue**: Immediate import of entire Rich UI framework
- **Impact**: Loads 15+ Rich components (Console, Markdown, Live, Panel, Table, etc.)
- **Files affected**: All CLI operations trigger this import chain
- **Priority**: HIGH - UI components used in every CLI session

#### 2. **Synchronous Network Operations**
- **Models.dev API**: `src/tunacode/utils/models_registry.py:188-193` - Blocking HTTP request with 10s timeout
- **Version checking**: `src/tunacode/utils/system.py:257-259` - Subprocess call to PyPI for update checks
- **Impact**: Network latency directly affects startup time
- **Current mitigation**: Update check moved to background thread

#### 3. **AI/ML Library Imports** (`src/tunacode/core/agents/agent_components/agent_config.py`)
- **Issue**: pydantic_ai and all tools imported immediately
- **Impact**: Heavy ML framework initialization at startup
- **Files affected**: All agent operations
- **Priority**: HIGH - Core functionality

#### 4. **Synchronous File I/O Operations**
- **Configuration loading**: `src/tunacode/utils/user_configuration.py:38-39` - Blocking JSON parsing
- **Template loading**: `src/tunacode/templates/loader.py:58-59` - Synchronous template file reads
- **Cache operations**: `src/tunacode/utils/models_registry.py:178-179` - Cache file reads/writes
- **Impact**: File system operations block main thread

#### 5. **Database Operations**
- **RAG indexer**: `llm-agent-tools/rag_modules/indexer.py:27` - SQLite connection setup
- **Connection pattern**: New connection for each operation (no connection pooling)
- **Schema setup**: FTS5 table creation and optimization
- **Impact**: Database setup adds overhead during first use

### Key Patterns Identified

#### **Eager Loading Pattern**
- UI components loaded immediately regardless of usage
- All agent tools imported at agent creation time
- Configuration parsed synchronously at startup
- No lazy loading for heavy dependencies

#### **Network at Import Time**
- Models.dev API calls during registry initialization
- Version checking via subprocess to PyPI
- MCP server connections established during agent creation

#### **Synchronous I/O Chain**
1. Package import → logging setup
2. Main entry → configuration loading
3. Agent creation → tool registration
4. Models registry → HTTP request
5. REPL start → directory scanning

### Current Optimizations in Place

#### **Background Processing**
- CodeIndex pre-warming in `repl.py:412-418` using `asyncio.create_task()`
- Update check moved to background thread in `main.py:65`
- Non-blocking directory caching

#### **Caching Strategies**
- Configuration fingerprinting in `config_setup.py:59-76` using SHA1 hashes
- Models registry cache with 24-hour TTL
- Directory listing cache with 5-second TTL
- Fast path caching to avoid reprocessing unchanged data

#### **Singleton Patterns**
- Global CodeIndex instance for directory caching
- Centralized logging configuration
- Shared models registry

### Performance Impact by Component

| Component | Startup Impact | Current Mitigation | Optimization Potential |
|-----------|----------------|-------------------|-----------------------|
| Rich UI Framework | High | None | Lazy loading, conditional imports |
| pydantic_ai | High | None | Deferred agent creation |
| Configuration Loading | Medium | Fingerprint caching | Async loading, memory caching |
| Models.dev API | Medium | 24hr cache | Background refresh, fallbacks |
| Database Operations | Low | Connection cleanup | Connection pooling |
| File System I/O | Low | Background processing | aiofiles, selective scanning |

### Root Cause Analysis

The startup performance issues stem from three architectural patterns:

1. **Import-time side effects**: Heavy operations performed during module import rather than explicit initialization
2. **Synchronous blocking operations**: File I/O, network requests, and parsing that block the main thread
3. **Eager dependency loading**: Loading entire frameworks and toolsets regardless of actual usage

### Data Flow During Startup

```
tunacode command
    ↓
cli/main.py (package import)
    ↓
__init__.py → setup_logging() (synchronous)
    ↓
load_config() (blocking file I/O)
    ↓
main() → ApplicationSettings (instantiation)
    ↓
StateManager, ToolHandler creation
    ↓
Rich UI components import
    ↓
Agent creation → pydantic_ai + tools import
    ↓
REPL start → background CodeIndex pre-warming
```

## Key Patterns / Solutions Found

- **Configuration fingerprinting**: SHA1 hash-based cache invalidation avoids unnecessary reloads
- **Background pre-warming**: CodeIndex builds in separate thread to avoid blocking startup
- **Singleton caching**: Global instances for expensive-to-create objects
- **Timeout-based fallbacks**: Network operations have timeouts and graceful degradation

## Knowledge Gaps

- **Actual timing measurements**: Need startup_timer.py results to quantify bottlenecks
- **User environment variance**: Performance impact on different systems/networks
- **Cache hit rates**: Effectiveness of current caching strategies
- **Memory usage impact**: Trade-offs between caching and memory consumption

## Recommendations for Optimization (Priority Order)

### HIGH PRIORITY
1. **Lazy load Rich UI components**: Only import when console operations are needed
2. **Defer pydantic_ai import**: Initialize AI framework only when agents are used
3. **Async configuration loading**: Move config parsing to background with graceful fallback

### MEDIUM PRIORITY
4. **Background models registry refresh**: Update cache in background, use stale data if needed
5. **Selective tool loading**: Import agent tools only when specific functionality is used
6. **Connection pooling**: Reuse database connections for RAG operations

### LOW PRIORITY
7. **File system optimization**: Use aiofiles for asynchronous file operations
8. **Template caching**: Pre-compile and cache templates
9. **Directory scanning optimization**: More selective file system scanning

## References

### Critical Files to Review
- **Primary entry point**: https://github.com/alchemiststudiosDOTai/tunacode/blob/83e26cc/src/tunacode/cli/main.py
- **UI framework loading**: https://github.com/alchemiststudiosDOTai/tunacode/blob/83e26cc/src/tunacode/ui/console.py
- **Configuration system**: https://github.com/alchemiststudiosDOTai/tunacode/blob/83e26cc/src/tunacode/core/setup/config_setup.py
- **Agent initialization**: https://github.com/alchemiststudiosDOTai/tunacode/blob/83e26cc/src/tunacode/core/agents/agent_components/agent_config.py
- **Models registry**: https://github.com/alchemiststudiosDOTai/tunacode/blob/83e26cc/src/tunacode/utils/models_registry.py
- **RAG indexer**: https://github.com/alchemiststudiosDOTai/tunacode/blob/83e26cc/llm-agent-tools/rag_modules/indexer.py
- **Startup timing utility**: https://github.com/alchemiststudiosDOTai/tunacode/blob/83e26cc/scripts/startup_timer.py

### Performance Scripts
- **Startup timing**: `scripts/startup_timer.py` - Use to measure current baseline
- **Environment verification**: `scripts/verify_dev_env.sh` - Check system configuration

### Configuration Files
- **Project settings**: `pyproject.toml` - Entry point configuration
- **Package structure**: Various `__init__.py` files controlling import behavior
