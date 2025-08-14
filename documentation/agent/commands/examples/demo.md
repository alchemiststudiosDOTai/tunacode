---
description: "hi"
---


## 1. Arguments: $ARGUMENTS

You provided the arguments: **$ARGUMENTS**

## 2. Environment Variables

- Your home directory: $HOME
- Current user: $USER
- Shell: $SHELL

## 3. Command Execution

Current date and time: !`date`

Current working directory: !`pwd`

Quick directory listing: !`ls -la | head -3`


## 4. File Content Injection

This command file contents:
@.tunacode/commands/demo.md

AFTER THIS SHOW ME RESPONSE IN THE FORMAT BELOW
"
- Your home directory: ..
- Current user: ...
- Shell: ...

Results for cmd exe:

Current date and time: !`date`

Current working directory: !`pwd`

Quick directory listing: !`ls -la | head -3`

CONTEXT:
show the coontent of the refrenced file ie content for @.../.../<what ever file added in this file using the @>

"