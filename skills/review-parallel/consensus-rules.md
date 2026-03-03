# Consensus Rules

Severity-based consensus algorithm for aggregating independent reviewer outputs.

## Algorithm

```
1. Each reviewer outputs: [{file, line, issue, severity, category}]

2. Group by (file, line_range) — within 5 lines = "same location"
   - If two issues target lines 42 and 45 in the same file, they are one group
   - If they target lines 42 and 50, they are separate groups

3. For each group:
   a. Count distinct reviewers who flagged it
   b. Take highest severity assigned by any reviewer
   c. Apply threshold:
      - CRITICAL >= 1 reviewer --> include in todo.md
      - MAJOR    >= 2 reviewers --> include in todo.md
      - MINOR    >= 3 reviewers --> include in todo.md
      - LOW      --> logged only, never included

4. Run survivors through actionability check:
   "Would a senior engineer change code based on this?"
   - YES --> keep
   - NO  --> drop (log reason)

5. Write to impl-tmp/todo.md ordered by:
   - severity DESC (CRITICAL > MAJOR > MINOR)
   - then vote_count DESC (more reviewers = higher confidence)

6. Early exit: if total surviving issues < 2, stop iterating

7. Hard cap: 3 iterations maximum
```

## Disagreement Handling

- **Contradictory suggestions** (reviewer A says "add X", reviewer B says "remove X"): Neither included unless one meets the severity threshold independently. Log the disagreement.
- **Same location, different angles**: Deduplicate by code location. Keep the highest severity. Cross-reviewer agreement is a confidence signal, not a reason to duplicate.
- **One critical, others disagree**: CRITICAL flags from Security or Correctness reviewers are auto-included regardless of other reviewers' opinions.

## todo.md Format

```markdown
# Review Issues

## CRITICAL
- [ ] **file.ext:42** — [security] SQL injection in user input handling (5/5 reviewers)

## MAJOR
- [ ] **file.ext:87** — [correctness] Off-by-one in pagination logic (3/5 reviewers)

## MINOR
- [ ] **file.ext:120** — [performance] O(n^2) loop in data processing (3/5 reviewers)
```

## Iteration Rules

| Iteration | Scope | Notes |
|-----------|-------|-------|
| 1 | Full codebase | All files reviewed |
| 2 | Diff only | Only changes from iteration 1 fixes |
| 3 | Diff only | Only changes from iteration 2 fixes; escalate remaining CRITICAL to human |
