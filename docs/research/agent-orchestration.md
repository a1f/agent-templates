# Research: Multi-Agent Orchestration Patterns

## Current State of the Art

The field has converged on several key patterns for LLM-based multi-agent systems. Major frameworks: LangGraph 1.0, Google ADK, CrewAI, OpenAI Agents SDK, Claude Code subagents.

## Key Decision: State Passing Between Phases

### Recommendation: Markdown Files + JSON Manifest

Use **markdown files on disk** as the primary state medium (native to coding agents), enhanced with a lightweight JSON manifest for orchestrator decisions.

```json
{
  "phase": 1,
  "status": "complete",
  "outputs": {
    "code_spec": "impl-tmp/code-spec.md",
    "test_plan": "impl-tmp/test-plan.md"
  },
  "timestamp": "2026-03-02T10:30:00Z"
}
```

**Rationale:** Anthropic's context engineering guide recommends file-based state with progressive disclosure. Agents write full artifacts to disk; only short summaries flow through the orchestrator.

**Alternatives rejected:**
- Structured JSON only: not human-readable for debugging
- Shared conversation context: context window bloat, expensive

## Key Decision: Error Recovery

### Recommendation: 3-Tier Strategy

| Tier | Pattern | Handles |
|------|---------|---------|
| 1 | Per-agent retry (max 2) | Transient API failures, malformed output |
| 2 | Phase-level checkpoint + rollback | Phase failures after retries |
| 3 | Graceful degradation for parallel agents | One of N agents fails |

Checkpoints written to `impl-tmp/checkpoint.json` before each phase. If a phase fails, roll back and re-dispatch. If one parallel agent fails, continue with the successful one and retry only the failed agent.

**Source:** Layered resilience stack reduced unrecoverable failures from 23% to under 2% (Klement Gunndu, 2025).

## Key Decision: Coordination Pattern

### Recommendation: Orchestrator-Worker with Blackboard State

The current design (orchestrator dispatches to workers) is correct. Enhance with blackboard-style state: `impl-tmp/` directory serves as the shared blackboard. Each agent writes to unique files (no conflicts).

**Alternatives rejected:**
- Peer-to-peer debate: voting beats consensus by 13.2% for reasoning tasks (ACL 2025)
- Hierarchical delegation: adds latency, overkill for this pipeline

## Key Decision: Intermediate Results

### Recommendation: File Artifacts + Short Summaries

Each subagent:
1. Writes full output to `impl-tmp/<artifact>.md`
2. Returns structured summary to orchestrator (not full artifact)
3. Next phase agents read files directly

Keeps orchestrator context lean. JetBrains Research (Dec 2025) confirmed this dramatically improves downstream agent performance.

## Key Decision: Worktrees vs File Separation

### Recommendation: File-Based Separation (No Worktrees)

| Phase | Agents | File Conflict Risk |
|-------|--------|-------------------|
| Phase 1 | Code Planner + Test Planner | None (different output files) |
| Phase 2 | Impl Coder + Test Coder | Low (different file types) |
| Phase 3 | 3 Reviewers | None (read-only) |
| Phase 4 | 5 Reviewers | None (read-only) |

Worktrees add unnecessary merge complexity for this use case.

## Key Decision: Review Iterations

### Recommendation: Cap at 3 (not 5)

Research shows debugging capability decays 60-80% after 2-3 attempts (Nature Scientific Reports, 2025). Add early-exit: if iteration N produces <2 new issues, stop.

Consider diff-only re-review on iterations 2-3 (reviewers examine only changes since last review).

## Sources

- [Effective Context Engineering - Anthropic](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [Voting or Consensus? (ACL 2025)](https://arxiv.org/abs/2502.19130)
- [SagaLLM (VLDB 2025)](https://arxiv.org/abs/2503.11951)
- [Debugging Effectiveness Decay (Nature)](https://www.nature.com/articles/s41598-025-27846-5)
- [4 Fault Tolerance Patterns for AI Agents](https://dev.to/klement_gunndu/4-fault-tolerance-patterns-every-ai-agent-needs-in-production-jih)
- [JetBrains: Context Management for LLM Agents](https://blog.jetbrains.com/research/2025/12/efficient-context-management/)
