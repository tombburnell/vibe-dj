# Agent Prompts & Standards

This directory contains prompts and standards for AI agents working on this codebase.

## Files

### `code-review.md`

Comprehensive code review agent prompt. Use this agent to review PRs and branches for:

- Correctness, security, performance, maintainability
- Alignment with requirements and standards
- Testing coverage and quality
- Code cleanliness and best practices

**Usage**: Reference this file when running code reviews. The agent will check against `code-standards.md` automatically.

### `code-standards.md` (moved from `agents/`)

Definitive coding standards and best practices document. This should be referenced by:

- **Coding agents** during implementation
- **Code review agents** during reviews
- **Developers** as a reference

**Key Sections**:

- Architecture & Separation of Concerns
- Type Safety & TypeScript
- Testing Requirements
- Security Standards
- Performance Guidelines
- Code Quality & Maintainability
- Frontend/Backend-Specific Standards
- Code Cleanliness

**Usage**:

- When writing code, check this document to ensure compliance
- When reviewing code, validate against these standards
- When updating patterns, update this document

### `draft-tech-approach.md`

Guide for creating technical approach documents (`docs/plans/*/tech-approach.md`). Use this when planning new features or major technical decisions.

**Key Sections**:

- Document structure (TLDR, TOC, sections)
- Comparison tables with recommendations
- ASCII diagrams for workflows
- Open questions identification
- Risk mitigation
- Noise reduction guidelines

**Usage**:

- When creating a new `tech-approach.md` document
- When reviewing technical approach documents
- To ensure consistent structure and decision-making clarity

### `review-tech-approach.md`

Guide for reviewing technical approach documents before implementation begins.

**Key Sections**:

- Pattern validation (verify referenced patterns exist)
- Base class contract verification (CRITICAL - catches most implementation bugs)
- Gap analysis (spec coverage, pattern consistency)
- Ambiguity detection

**Usage**:

- Before approving a tech approach for implementation
- To catch missing inherited method documentation
- To verify patterns match actual codebase

### `review-plan.md`

Guide for reviewing implementation plans before development starts.

**Key Sections**:

- Tech approach alignment
- Implementation detail review (sufficient for devs to proceed without guessing)
- Base class contract verification
- Traceability (spec → plan, tech approach → plan)

**Usage**:

- Before starting development on a plan
- To catch ambiguous instructions that cause implementation bugs
- To verify all abstract methods are explicitly documented

## Integration

### For Coding Tasks

1. Reference `code-standards.md` at the start of coding tasks
2. Check the "Quick Reference Checklist" before completing code
3. Ensure all code follows the examples and avoids anti-patterns

### For Code Reviews

1. The `code-review.md` agent automatically references `code-standards.md`
2. All findings should align with standards documented there
3. Use standards as the basis for severity assessment

### For Technical Planning

1. Read `agents/draft-tech-approach.md` when creating `tech-approach.md` documents
2. Ask key questions before drafting (see guide)
3. Follow the structure and checklist in the guide
4. Ensure recommendations are clear and open questions are identified

### For Updating Standards

1. When new patterns emerge or issues are found, update `code-standards.md`
2. Keep examples current with actual codebase patterns
3. Update the "Last Updated" section when making changes

## Quick Start

**Writing Code**:

```
1. Read code-standards.md
2. Follow the Quick Reference Checklist
3. Reference examples for your layer (Frontend/Backend)
4. Avoid all listed anti-patterns
```

**Reviewing Code**:

```
1. Use agents/code-review.md prompt
2. Agent will automatically check against docs/code-standards.md
3. Findings will reference specific standards sections
```

**Planning Technical Approach**:

```
1. Read docs/plans/[ticket]/spec.md to understand requirements
2. Reference agents/draft-tech-approach.md for structure
3. Ask key questions (see guide)
4. Research existing codebase patterns
5. Draft tech-approach.md following guide structure
6. Review against checklist before finalizing
```

## Maintenance

- **Update frequency**: When patterns change or new issues are discovered
- **Ownership**: Team maintains these documents collectively
- **Versioning**: Update "Last Updated" section when making changes
- **Feedback**: Incorporate learnings from code reviews into standards
