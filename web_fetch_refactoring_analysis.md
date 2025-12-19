# Web Fetch Tool Refactoring Analysis

## Issue 1: "Magic Numbers" (Line 16-17)

### Current Code
```python
# this is magic numbers or is it need to review this down the road
MAX_CONTENT_SIZE = 5 * 1024 * 1024    # 5MB
MAX_OUTPUT_SIZE = 100 * 1024           # 100KB  
DEFAULT_TIMEOUT = 60                   # 60 seconds
```

### Problem Analysis

**What are the "magic numbers"?**
- Hardcoded values chosen without clear documentation
- No ability for users to configure based on their needs
- Arbitrary limits that may not suit all use cases

**Why this is problematic:**

1. **No Configuration Flexibility**
   - Users with slow networks might want smaller timeouts
   - Users scraping large documentation sites might want larger content limits
   - Mobile users might want smaller output limits to save bandwidth

2. **No Rationale Documentation**
   - Why 5MB and not 10MB or 1MB?
   - Why 60 seconds and not 30 or 120?
   - Why 100KB output limit?
   - No performance or memory usage justification

3. **Maintenance Burden**
   - Changing values requires code modification
   - Different environments (dev/staging/prod) might need different values
   - No runtime adjustment capability

### Current Impact

- Users hitting arbitrary limits with no recourse
- Support tickets for "content too large" when size is reasonable for their use case
- Inability to optimize for specific environments (e.g., CI/CD with faster networks)

### Proposed Solutions

#### Option 1: User Configuration (Recommended)
```python
# In user_config.json or similar
{
  "settings": {
    "web_fetch": {
      "max_content_size_mb": 5,
      "max_output_size_kb": 100, 
      "default_timeout_seconds": 60
    }
  }
}
```

#### Option 2: Environment Variables
```bash
TUNACODE_WEB_FETCH_MAX_CONTENT_SIZE_MB=5
TUNACODE_WEB_FETCH_MAX_OUTPUT_SIZE_MB=0.1
TUNACODE_WEB_FETCH_DEFAULT_TIMEOUT=60
```

#### Option 3: Function Parameters with Defaults
```python
async def web_fetch(
    url: str, 
    timeout: int = DEFAULT_TIMEOUT,
    max_content_size: int = None,
    max_output_size: int = None
) -> str:
```

### Recommended Implementation

1. **Phase 1**: Add configuration support with existing defaults
2. **Phase 2**: Add runtime parameter overrides  
3. **Phase 3**: Add documentation explaining the rationale for defaults

### Risk Assessment

**Low Risk:**
- Backward compatibility maintained with existing defaults
- Changes are additive, not breaking

**Medium Risk:**
- Configuration validation needed
- Error handling for invalid user values

**Testing Requirements:**
- Test with various config values
- Test invalid config handling
- Test default behavior remains unchanged

---

## Other Issues Identified (Brief)

### Issue 2: Regex Pattern Anti-Pattern (Line 22-23)
Repeated regex compilation for IP validation - could use standard library

### Issue 3: Duplicate IP Validation Logic (Line 49)
Both regex patterns AND ipaddress module doing similar work

### Issue 4: Wordy Validation Function (Line 62)
_validate_url function is doing too much and could be simplified

### Issue 5: Non-Stealthy User-Agent (Line 132)
User-Agent string identifies as automated tool, may get blocked

### Issue 6: Repetitive Exception Handling (Line 171)
Similar error message patterns repeated across exception types