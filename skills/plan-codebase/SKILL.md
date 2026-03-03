---
name: plan-codebase
description: Use when dispatched by implement-orchestrator to create a code specification from an approved plan, or when you need to analyze a codebase and produce a detailed implementation specification
---

# Plan Codebase

Produce a file-by-file code specification (`impl-tmp/code-spec.md`) from an approved `plan.md` by analyzing the existing codebase and applying clean-code principles.

## When to Use

- Dispatched by implement-orchestrator as Phase 1a
- Manually invoked to generate a code specification before implementation

## Prerequisites

- `plan.md` exists in the working directory

## The Process

### 1. Read the Plan

Read `plan.md` end-to-end. Extract every requirement, feature, and acceptance criterion. Note any explicit file paths, APIs, or constraints mentioned.

### 2. Scan the Codebase

Explore the codebase systematically:
- Grep for existing functions, classes, and modules related to the plan's domain
- Read key entry points, configuration files, and existing abstractions
- Identify reuse opportunities -- existing utilities, shared types, helper functions
- Map the current directory structure and module boundaries
- Note the language, framework, and testing patterns in use

### 3. Classify and Plan Each Change

For every requirement in the plan, determine the exact files to create, modify, or delete. For each file change:
- Write the rationale (why this file changes)
- Describe each modification with pseudo-code or a code skeleton
- List dependencies on other files in the spec

### 4. Apply Clean-Code Principles

Before finalizing the spec, review every planned change against:
- **DRY:** Does this duplicate anything already in the codebase? Can existing code be reused?
- **SRP:** Does each new file/function have a single responsibility?
- **Dependency direction:** Do imports point from volatile toward stable?
- **Naming:** Do names reveal intent?
- **Extraction:** Should any planned function be split for testability or reuse?

**REQUIRED SUB-SKILL:** clean-code-planner

### 5. Write code-spec.md

Write the structured specification to `impl-tmp/code-spec.md` following the output format defined in the prompt template (`codebase-planner-prompt.md`).

### 6. Return Summary

Return a short summary to the orchestrator (not the full spec):
- Number of files to create, modify, delete
- Key architectural decisions made
- Any risks or ambiguities found in the plan

## Quick Reference

| Step | Action | Output |
|------|--------|--------|
| 1 | Read plan.md | Requirements list |
| 2 | Scan codebase | Reuse map, patterns found |
| 3 | Classify changes | File-by-file change list |
| 4 | Apply clean-code | Refined spec |
| 5 | Write spec | `impl-tmp/code-spec.md` |
| 6 | Summarize | Short summary to orchestrator |

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Skipping codebase scan | Always grep before proposing new files |
| Duplicating existing utilities | Search for existing implementations first |
| Monolithic changes in one file | Split by responsibility |
| Missing dependency listings | Every file change must list its dependencies |
| Writing full implementation instead of spec | Write pseudo-code and skeletons, not final code |
