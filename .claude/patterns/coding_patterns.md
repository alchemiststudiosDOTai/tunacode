# Coding Patterns

1. **Guard Clause** - Flatten nested conditionals by returning early, so pre-conditions are explicit
2. **Delete Dead Code** - If it's never executed, delete it – that's what VCS is for
3. **Normalize Symmetries** - Make identical things look identical and different things look different for faster pattern-spotting
4. **New Interface, Old Implementation** - Write the interface you wish existed; delegate to the old one for now
5. **Reading Order** - Re-order elements so a reader meets ideas in the order they need them
6. **Cohesion Order** - Cluster coupled functions/files so related edits sit together
7. **Move Declaration & Initialization Together** - Keep a variable's birth and first value adjacent for comprehension & dependency safety
8. **Explaining Variable** - Extract a sub-expression into a well-named variable to record intent
9. **Explaining Constant** - Replace magic literals with symbolic constants that broadcast meaning
10. **Explicit Parameters** - Split a routine so all inputs are passed openly, banishing hidden state or maps
