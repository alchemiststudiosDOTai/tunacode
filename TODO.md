

### 1. Session Naming Strategy
What approach do you prefer for user-friendly session names?

**Option A: Timestamp + Auto-description**
- Format: `2025-01-23_14-30_python-debugging-session`
- Auto-generate description from first few messages
- Fallback to generic names if content unclear
- when a user runs /resume, we list all sessions with this format and the usr will scroll and choose

### 2. Message Data Preservation
How comprehensive should we be with message serialization?

- Basic session data, stuff like keys are NOT to be saved 
- the chat, the users query and the agents response
- tool calls 




### 3. Backward Compatibility
- NONE this is brand new wee jabvent relased this yes 

### 4. Implementation Scope
Given the research shows this touches multiple files and tests, should we:
- Start with just the naming improvement 
- then update the SINGHULAR test for this 
- then move to the message serialization, users query and aigent response should be saved in a formatted way 

- go slow, explore and implement this with the least amount of code changes

DO NOT CODE, CREATE A DOCUMENT CALLED " PLAN" BEFORE WE BEGIN TO OUTLINE THE WORK IN PHASES MAX 3 PHAES MAX 3 SUBPHASES 

