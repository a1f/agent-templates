# Research: Automated Code Review & Consensus Mechanisms

## Current State of the Art

Leading tools (RovoDev at Atlassian, CodeRabbit, GitHub Copilot) use multi-stage pipelines: static analysis first, then LLM review, then filtering. Key insight: filtering for "will a developer act on this?" matters more than "is this factually correct?" (RovoDev: 15pp improvement from actionability ranking).

## Consensus Mechanism

### Recommendation: Severity-Weighted Threshold

```
CRITICAL (security, crashes, data corruption): ≥1 reviewer → todo.md
MAJOR (logic errors, spec violations):         ≥2 reviewers → todo.md
MINOR (maintainability, minor perf):           ≥3 reviewers → todo.md
LOW (style nits, suggestions):                 Logged only, not required
```

**Why not flat ≥3/5:** A Security Reviewer flagging SQL injection shouldn't be overruled because 4 other reviewers weren't looking for it.

**Why not debate/consensus:** Research shows voting outperforms debate by 13.2% for reasoning tasks. Sycophancy (agents abandoning correct answers to agree with peers) is the dominant failure mode in multi-agent debate.

## Reviewer Independence

### Recommendation: Fully Independent (No Visibility)

All 5 reviewers run in parallel with NO visibility into each other's output. Aggregate results mechanically.

**Evidence:**
- Sycophancy is lowest in first round, progressively worsens (Peacemaker or Troublemaker, arXiv 2025)
- Independent reviews preserve answer diversity
- "All-Agents Drafting" pattern yields 3.3% improvement over shared context

## Reviewer Categories

### Recommendation: 5 Refined Categories

| # | Reviewer | Focus | Rationale |
|---|----------|-------|-----------|
| 1 | **Correctness** | Logic errors, edge cases, null handling, race conditions | Highest resolution rate. Broadened from "Bug Hunter" |
| 2 | **Spec Compliance** | Plan.md vs actual code | Unique to agentic workflows. No commercial tool does this |
| 3 | **Security** | OWASP top 10, injection, auth, data exposure | Non-negotiable. Can flag issues unilaterally (severity=critical) |
| 4 | **Maintainability** | Readability, DRY, complexity, testability | Merges Style + Maintainability. Pure style better handled by linters |
| 5 | **Performance** | O(n²) loops, memory leaks, unnecessary allocations | Hard to catch post-merge |

## False Positive Reduction

Layered approach (ordered by impact):
1. **Actionability check** — "Would a senior engineer change code based on this?" (biggest lever, 15pp improvement)
2. **Consensus filtering** — severity-based thresholds as above
3. **Structured prompts** — precise reviewer mandates with explicit "what NOT to flag"
4. **Tight context** — only relevant code, not full codebase (CodeRabbit's key insight)

## Disagreement Handling

- **Contradictory suggestions**: Neither included unless meets severity threshold. Log disagreement.
- **Same location, different angles**: Deduplicate by code location. Keep highest severity. Cross-reviewer agreement = confidence signal.
- **One critical, others disagree**: Security/Correctness critical flags auto-included regardless.

## Implementation: consensus-rules.md Logic

```
1. Each reviewer outputs: [{file, line, issue, severity, category}]
2. Group issues by (file, line_range) — within 5 lines = "same location"
3. For each group:
   a. Count distinct reviewers who flagged it
   b. Take highest severity assigned
   c. Apply threshold: CRITICAL≥1, MAJOR≥2, MINOR≥3
4. Run surviving issues through actionability prompt
5. Write to todo.md, ordered by severity desc, then vote_count desc
6. If total issues < 2, stop iterating
7. Max 3 iterations
```

## Sources

- [RovoDev at Atlassian (ICSE 2026)](https://arxiv.org/html/2601.01129v1)
- [Voting or Consensus? (ACL 2025)](https://aclanthology.org/2025.findings-acl.606/)
- [Sycophancy in Multi-Agent Debate](https://arxiv.org/html/2509.23055v1)
- [CodeRabbit Architecture](https://docs.coderabbit.ai/overview/architecture)
- [Datadog: LLMs to Filter False Positives](https://www.datadoghq.com/blog/using-llms-to-filter-out-false-positives/)
- [Atlassian: Comment Resolution Rates](https://www.atlassian.com/blog/atlassian-engineering/atlassian-rovo-dev-research-what-types-of-code-review-comments-do-developers-most-frequently-resolve)
