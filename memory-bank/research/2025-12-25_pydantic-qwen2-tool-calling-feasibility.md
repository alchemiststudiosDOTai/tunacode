---
type: deep-search
query: "Can Pydantic handle Qwen2-style tool calling pattern (parsing JSON from unstructured text, XML tags, code fences)?"
date: 2025-12-25
sources: [exa-code, gemini]
---

# Deep Search: Can Pydantic Handle Qwen2-Style Tool Calling?

## Query Analysis

- **Perspective 1**: Pydantic's native capabilities for parsing JSON from unstructured text sources
- **Perspective 2**: Pydantic extensions for XML parsing and custom validators
- **Perspective 3**: Alternative libraries (msgspec, dirty-equals) and complementary tools (json-repair)

## Executive Summary

**Pydantic CANNOT handle the Qwen2-style tool calling pattern natively.** Pydantic is a **strict validation library** by design - it expects valid JSON strings or Python dictionaries. It cannot:

1. Search through unstructured text to find JSON blobs
2. Extract JSON from XML tags like `````<tool_call>...````
3. Handle malformed JSON (missing quotes, trailing commas, Python `None` vs `null`)
4. Parse from code fences or mixed garbage text

## Findings by Source

### Exa Code Results (Pydantic Documentation & Examples)

**Key Insights:**
- Pydantic validators (`@field_validator`) operate **after** input is received, not for extraction
- Custom validators can transform values but expect already-parsed data
- `model_validate_json()` expects a **valid JSON string** - raises `ValidationError` on any syntax error
- `PydanticOutputParser` in LangChain requires pre-extracted JSON content

**Relevant Patterns:**
```python
# Pydantic expects this flow:
raw_text -> [EXTRACTION] -> json_string -> model_validate_json() -> Model
#            ^ NOT Pydantic's job
```

### Gemini Search Results (Real-time Google Grounding)

**Key Findings:**

1. **Parsing JSON from Unstructured Text**: Pydantic cannot search through text to find JSON. Must use regex first:
   ```python
   match = re.search(r'\{.*\}', text, re.DOTALL)
   if match:
       json_str = match.group()
       data = json.loads(json_str)
       model = MyModel.model_validate(data)
   ```

2. **Handling Malformed JSON**: Pydantic raises `ValidationError` on syntax errors. Solution:
   - Use **`json-repair`** library (or Rust-based `fast-json-repair`)
   - Workflow: `Raw Text -> json_repair -> Valid JSON -> Pydantic`

3. **XML Parsing**: Pydantic has no built-in XML support. Solution:
   - Use **`pydantic-xml`** extension for structured XML
   - For extracting JSON *from* XML tags (like `````<tool_call>```{...}``` </tool_call>```), regex is still required first

4. **Alternatives Comparison**:
   - **`msgspec`**: Equally strict as Pydantic, not a fuzzy parser. Faster but doesn't solve the unstructured text problem.
   - **`dirty-equals`**: This is a **testing assertion library** (`assert data == IsInt()`), NOT a production parser for data cleaning.

## Synthesis

### Consensus

All sources agree: **Pydantic is strictly for validation, not extraction or repair**. The library is designed around the philosophy that input should be clean before validation.

### Contradictions

No significant contradictions found. All documentation and community guidance point to the same architectural pattern: extract/repair first, validate second.

### Key Insights

**For the Qwen2-Style Tool Calling Pattern:**

The current parser implementation in `tunacode-finetuning/src/tunacode_training/eval/parser.py` is **the correct approach**. A multi-strategy extraction with regex patterns, followed by JSON parsing, is necessary because:

1. **No single library does it all** - The pattern requires:
   - Regex extraction (custom code)
   - JSON repair (optional `json-repair`)
   - Validation (Pydantic could work here)

2. **Pydantic adds no value to the extraction phase** - It cannot replace the 5-strategy parser:
   - Strategy 1: `````<tool_call>``` tags (needs regex)
   - Strategy 2: Direct JSON object (needs brace-balancing logic)
   - Strategy 3: ```json code blocks (needs regex)
   - Strategy 4: Loose JSON matching (needs regex)
   - Strategy 5: Fallback name-only (needs regex)

3. **Where Pydantic COULD help**: After extraction, for **schema validation**:
   ```python
   class ToolCall(BaseModel):
       name: str
       arguments: dict[str, Any]

   # After extraction succeeds:
   validated = ToolCall.model_validate(extracted_data)
   ```

## Recommended Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Raw Model Output (unstructured text)                       │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       v
┌─────────────────────────────────────────────────────────────┐
│  Multi-Strategy Extractor (CURRENT PARSER)                  │
│  - Regex for <tool_call> tags                               │
│  - Brace balancing for direct JSON                          │
│  - Code fence detection                                     │
│  - Loose JSON patterns                                      │
│  - Name-only fallback                                       │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       v
┌─────────────────────────────────────────────────────────────┐
│  Optional: json-repair (if JSON is malformed)              │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       v
┌─────────────────────────────────────────────────────────────┐
│  Pydantic Validation (OPTIONAL UPGRADE)                     │
│  - Validate tool name against allowed tools                 │
│  - Validate argument schemas                                │
│  - Type checking                                            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       v
┌─────────────────────────────────────────────────────────────┐
│  ParsedToolCall                                             │
│  - name: str                                                │
│  - arguments: dict[str, Any]                                │
│  - parse_success: bool                                      │
│  - parse_method: str                                        │
└─────────────────────────────────────────────────────────────┘
```

## Sources

- [Pydantic Custom Validators Documentation](https://docs.pydantic.dev/latest/examples/custom_validators) - via Exa Code
- [Pydantic JSON Validation](https://docs.pydantic.dev/latest/concepts/json/) - via Exa Code
- [json-repair Library](https://github.com/mangiucugna/json_repair) - via Gemini Search
- [pydantic-xml Extension](https://github.com/danillouz/pydantic-xml) - via Gemini Search
- [msgspec Documentation](https://jcristharif.com/msgspec/) - via Gemini Search
- [dirty-equals Documentation](https://github.com/davidhce/dirty-equals) - via Gemini Search

## Conclusion

**Pydantic alone cannot handle the Qwen2-style tool calling pattern.** The existing custom parser implementation is necessary and well-designed. Pydantic could optionally be added **after** extraction for schema validation, but it cannot replace the extraction logic itself.
