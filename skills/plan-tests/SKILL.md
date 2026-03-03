---
name: plan-tests
description: Use when dispatched by implement-orchestrator to create a test plan from an approved plan, or when you need to design a comprehensive test strategy for a feature
---

# Plan Tests

Produce a structured test plan (`impl-tmp/test-plan.md`) from an approved `plan.md` by discovering existing test patterns and defining test cases for every requirement.

## When to Use

- Dispatched by implement-orchestrator as Phase 1b (parallel with plan-codebase)
- Manually invoked to generate a test plan before implementation

## Prerequisites

- `plan.md` exists in the working directory

## The Process

### 1. Read the Plan

Read `plan.md` end-to-end. Extract every requirement and acceptance criterion. Note edge cases, error conditions, and constraints that need verification.

### 2. Discover Test Infrastructure

Explore the codebase for existing test patterns:
- Find test directories, naming conventions, and runner configuration
- Read config files (`pytest.ini`, `pyproject.toml`, `jest.config.*`, `package.json`, `Cargo.toml`, etc.)
- Read 2-3 existing test files to learn fixture patterns, assertion style, and helpers
- Identify shared test utilities, factories, and mock setups

### 3. Define Test Cases per Requirement

For each requirement, define test cases covering:
- Happy path (expected input produces expected output)
- Edge cases (boundary values, empty inputs, large inputs)
- Error paths (invalid input, missing dependencies, failure modes)
- Integration points (interactions between components)

### 4. Specify Fixtures, Mocks, and Test Structure

For each test case, specify:
- Setup requirements (fixtures, factories, test data)
- Services or dependencies to mock
- Exact file paths where tests should live (follow existing conventions)

### 5. Apply Language-Specific Testing Practices

Apply the relevant language rule from `rules/` for testing conventions (e.g., pytest fixtures for Python, vitest/jest for TypeScript, `#[cfg(test)]` for Rust, GTest/Catch2 for C++).

### 6. Write test-plan.md

Write the structured test plan to `impl-tmp/test-plan.md` following the output format defined in the prompt template (`test-planner-prompt.md`).

### 7. Return Summary

Return a short summary to the orchestrator:
- Test case count and requirement coverage
- Frameworks and fixtures identified
- Gaps or ambiguities in testability

## Quick Reference

| Step | Action | Output |
|------|--------|--------|
| 1 | Read plan.md | Requirements + acceptance criteria |
| 2 | Discover test infra | Framework, fixtures, conventions |
| 3 | Define test cases | Cases per requirement |
| 4 | Specify fixtures/mocks | Test structure |
| 5 | Apply language rules | Language-appropriate patterns |
| 6 | Write plan | `impl-tmp/test-plan.md` |
| 7 | Summarize | Short summary to orchestrator |

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Testing implementation details | Test behavior and public interfaces only |
| Ignoring existing test patterns | Always read existing tests first |
| Missing error/edge cases | Cover happy, edge, and error paths per requirement |
| Inventing a new test framework | Use whatever the project already uses |
| Overly coupled fixtures | Design fixtures for reuse across test files |
| Writing test code instead of a plan | Write structured descriptions, not code |
