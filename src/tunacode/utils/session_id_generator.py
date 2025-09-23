"""
Session ID generation utilities.

Provides user-friendly session ID generation with timestamp and auto-description.
Separated from session_utils to avoid circular imports with core.state.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any, List, Optional

# Session naming constants
MAX_DESCRIPTION_LENGTH: int = 20
FALLBACK_DESCRIPTION: str = "general-session"


def _generate_session_description(messages: List[Any]) -> str:
    """Generate a descriptive session name from the first few user messages.

    Extracts meaningful keywords from user queries to create a readable description.
    Falls back to generic description if no meaningful content is found.
    Handles both simple dict messages and enhanced message format with parts.
    """
    if not messages:
        return FALLBACK_DESCRIPTION

    # Extract text content from messages
    text_parts = []

    # Look at first 1-3 messages for user content
    for msg in messages[:5]:  # Look at more messages to find user content
        if isinstance(msg, dict):
            # Handle enhanced format with parts
            if "parts" in msg:
                for part in msg["parts"]:
                    if isinstance(part, dict):
                        # User prompt parts
                        if part.get("part_kind") == "user-prompt" or part.get("role") == "user":
                            content = part.get("content", "")
                            if isinstance(content, str):
                                text_parts.append(content)
            # Handle simple format
            elif msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    text_parts.append(content)
                elif isinstance(content, list):
                    # Handle structured content
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            text_parts.append(part.get("text", ""))

        # Stop after we have enough text content
        if len(text_parts) >= 2:
            break

    if not text_parts:
        return FALLBACK_DESCRIPTION
    
    # Combine and extract keywords
    combined_text = " ".join(text_parts).lower()
    
    # Look for common programming-related keywords
    keywords = []
    
    # File extensions and languages
    lang_patterns = [
        r'\b(python|py)\b', r'\b(javascript|js)\b', r'\b(typescript|ts)\b',
        r'\b(java)\b', r'\b(rust|rs)\b', r'\b(go)\b', r'\b(cpp|c\+\+)\b',
        r'\b(html|css)\b', r'\b(sql)\b', r'\b(bash|shell)\b'
    ]
    
    for pattern in lang_patterns:
        if re.search(pattern, combined_text):
            match = re.search(pattern, combined_text)
            if match:
                keywords.append(match.group(1))
                break
    
    # Common action words
    action_patterns = [
        r'\b(debug|debugging|fix|fixing|error|bug)\b',
        r'\b(test|testing|unit|integration)\b',
        r'\b(refactor|refactoring|optimize)\b',
        r'\b(implement|implementation|create|build)\b',
        r'\b(api|endpoint|server|client)\b',
        r'\b(database|db|query)\b'
    ]
    
    for pattern in action_patterns:
        if re.search(pattern, combined_text):
            match = re.search(pattern, combined_text)
            if match:
                keywords.append(match.group(1))
                break
    
    # File names (simple heuristic)
    file_matches = re.findall(r'\b\w+\.(py|js|ts|java|rs|go|cpp|html|css|sql|sh)\b', combined_text)
    if file_matches:
        # Take first file name without extension
        filename = file_matches[0][0]
        if len(filename) <= 10:
            keywords.append(filename)
    
    # Create description from keywords
    if keywords:
        description = "-".join(keywords[:2])  # Max 2 keywords
    else:
        # Extract first meaningful word
        words = re.findall(r'\b[a-zA-Z]{3,}\b', combined_text)
        if words:
            description = words[0]
        else:
            description = FALLBACK_DESCRIPTION
    
    # Sanitize and limit length
    description = re.sub(r'[^a-zA-Z0-9\-]', '-', description)
    description = re.sub(r'-+', '-', description).strip('-')
    
    if len(description) > MAX_DESCRIPTION_LENGTH:
        description = description[:MAX_DESCRIPTION_LENGTH].rstrip('-')
    
    return description if description else FALLBACK_DESCRIPTION


def generate_user_friendly_session_id(messages: Optional[List[Any]] = None) -> str:
    """Generate a user-friendly session ID with timestamp and description.

    Format: YYYY-MM-DD_HH-MM-SS_{slug}_{shortid}
    Example: 2025-01-23_14-30-45_python-debugging_a1b2c3
    """
    # CLAUDE_ANCHOR[canonical-session-id-generator]: Builds canonical UTC session IDs with shortid suffix
    now = datetime.utcnow()
    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")

    description = _generate_session_description(messages or [])

    # Add short hex suffix for uniqueness (6 lowercase hex chars)
    shortid = uuid.uuid4().hex[:6]

    return f"{timestamp}_{description}_{shortid}"
