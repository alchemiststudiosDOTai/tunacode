---
allowed-tools: Edit, View, Bash(gh:*)
description: Creates well-structured GitHub issues using gh CLI
---

# Create GitHub Issue

Create a comprehensive GitHub issue for: $ARGUMENTS

## Step 1: Repository Check

Verify we're in a GitHub repository and gather context.

## Step 2: Determine Issue Type

Based on "$ARGUMENTS", determine if this is a:

- Feature request (enhancement)
- Bug report
- Documentation update
- Performance improvement
- Other type

## Step 3: Draft Issue Content

Create a well-structured issue with:

- Clear, descriptive title
- Summary of the problem/request
- Detailed description
- Success criteria
- Implementation suggestions (if applicable)

## Step 4: Select Labels

Check available labels and select appropriate ones based on the issue type.

## Step 5: Create Issue

Use the gh CLI to create the issue with the drafted content and appropriate labels.

## Step 6: Provide Next Steps

After creation,show you the issue URL and suggest any follow-up actions like assigning users or adding to projects.

After the issue is made use the gh cli tool tag @coderabbitai ask the agent to make a document with key filelocations and logic for the next agent

You must do this AFTER the issue, do not create a document, coderabbitai will do this
