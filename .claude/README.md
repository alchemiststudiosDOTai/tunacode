.claude/
├── metadata/
│   ├── dependency_graphs/
│   ├── file_classifications.json (implementation vs. interface)
│   └── intent_classifications.json
├── semantic_index/
│   ├── function_call_graphs.json
│   ├── intent_mappings.json
│   └── type_relationships.json
├── debug_history/
│   ├── error_solution_logs.json (categorized by component and error type)
│   └── context_and_versions.json
├── patterns/
│   ├── canonical_patterns/
│   ├── empirical_interface_patterns/
│   └── reliability_metrics.json
├── qa/
│   ├── solved_problems/
│   ├── context_logs/
│   └── reasoning_docs/
├── debug_history/
│   └── debug_sessions.json (error→solution pairs, context, code versions)
├── delta_summaries/
│   ├── api_change_logs.json
│   ├── behavior_changes.json
│   └── reasoning_logs/
└── memory_anchors/
    ├── anchors.json (UUID-based anchors with semantic structure)
