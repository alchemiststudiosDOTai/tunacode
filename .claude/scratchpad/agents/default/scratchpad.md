# SWE-bench Style Benchmark Design
_Started: 2025-08-12 12:15:48_
_Agent: default

[1] Understanding SWE-bench Core Concepts: SWE-bench evaluates AI models on real GitHub issues by providing a codebase and issue description, then checking if generated patches resolve the problem using Docker-based evaluation
[2] Key Design Decisions for Simple Benchmark: (1) Use JSON format for test instances, (2) Focus on small, isolated code fixes, (3) Use pytest for evaluation, (4) Start with 2 problems from different domains
[3] Proposed Directory Structure: benchmarks/ with subdirs: instances/ (test problems), solutions/ (reference fixes), evaluation/ (test harness), results/ (outputs)
[4] Test Problem 1 - String Utility Bug: A simple string reversal function that fails on Unicode. Test Problem 2 - Math Calculation Error: A statistics function with incorrect edge case handling
[5] JSON Instance Format: {id, repo, problem_statement, base_code, test_file, expected_patch, metadata:{difficulty, category, created_date}}
