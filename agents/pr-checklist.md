# PR Quality Checklist

This checklist captures the most common issues found in PR reviews. Run through this before submitting a PR or as part of AI code review.

## How to Use

**For PR Authors**: Run through this checklist before requesting review.
**For AI Code Review**: Reference this checklist when reviewing changes.

---

## Checklist

### 1. Error Handling

- [ ] **1.1** Services and job processors throw errors on failure (not return null)
- [ ] **1.2** No empty catch blocks - all catches log errors with context
- [ ] **1.3** Errors include relevant context (IDs, operation name) for debugging
- [ ] **1.4** Job processors fail explicitly (throw) rather than completing silently

**Common violation**: Returning `null` in a catch block instead of throwing, making failures silent.

### 2. Architecture & Layer Separation

- [ ] **2.1** Routers are thin - only HTTP concerns, delegate to services
- [ ] **2.2** Business logic is in services, not routers or repositories
- [ ] **2.3** Queue/Redis operations are in orchestration layer, not repositories
- [ ] **2.4** No circular dependencies between modules

**Common violation**: Business logic or BullMQ operations in repository files.

### 3. Database & Schema

- [ ] **3.1** New tables have `created_at` (NOT NULL, defaultNow) and `updated_at` fields
- [ ] **3.2** Soft-deletable tables have `deleted_at` field
- [ ] **3.3** All queries on soft-deletable tables filter `WHERE deleted_at IS NULL`
- [ ] **3.4** Foreign keys have appropriate `onDelete` behavior (CASCADE, SET NULL, NO ACTION)
- [ ] **3.5** Tenant/organisation filtering is applied to all queries

**Common violation**: Queries that don't filter soft deletes, leaking "deleted" records.

### 4. Environment & Configuration

- [ ] **4.1** New env vars added to `.kamal/secrets-common`
- [ ] **4.2** New env vars documented in `.env.example` or README
- [ ] **4.3** Env vars have validation in `bff/src/utils/env.ts` with sensible defaults
- [ ] **4.4** No hardcoded values that should be configurable

**Common violation**: Adding env var to code but forgetting deployment configs.

### 5. BullMQ & Job Processing

- [ ] **5.1** Job processors throw on failure (never return null)
- [ ] **5.2** Job data is not mutated directly (use `job.updateData()`)
- [ ] **5.3** Correlation ID is included in all job-related logs
- [ ] **5.4** Jobs are idempotent (safe to retry)

**Common violation**: `job.data.field = value` instead of `job.updateData({...})`.

### 6. Queue Configuration & Job Optimization

- [ ] **6.1** No queue-level configuration without good reason and comments (rely on `defaults.ts`)
- [ ] **6.2** No explicit backoff configuration unless needed (file I/O = 1s, external APIs = 5s, default = 2s)
- [ ] **6.3** Use `AiJobCacheOptimizer.enqueueWithCacheWarming()` for bulk AI job enqueuing
- [ ] **6.4** Build job arrays first, then enqueue in bulk (not individual `queue.add()` in loops)

**Common violation**: Setting queue-level `queueOptions` that duplicate defaults, or using `await queue.add()` in loops instead of bulk operations.

### 7. Type Safety

- [ ] **7.1** No `any` types (use explicit types or `unknown` with guards)
- [ ] **7.2** Complex inline types extracted to named interfaces
- [ ] **7.3** Shared types used from `@shared/types` where applicable
- [ ] **7.4** Enums used for finite value sets (not string literals)

**Common violation**: Using `any` to "make it work" without proper typing.

### 8. Code Cleanliness

- [ ] **8.1** No console.log/debug statements
- [ ] **8.2** No commented-out code blocks
- [ ] **8.3** No TODO/FIXME without linked tickets
- [ ] **8.4** Unused imports, functions, and files removed
- [ ] **8.5** No experimental/debug code left in
- [ ] **8.6** No whitespace-only changes (revert with `git checkout origin/main -- <file>`)

**Common violation**: Leaving console.log statements from debugging, or committing files with only indentation changes.

### 9. Code Style

- [ ] **9.1** No nested ternary operators (use if/else)
- [ ] **9.2** Static arrays/objects defined as const outside render functions
- [ ] **9.3** Clear, descriptive naming (no typos)
- [ ] **9.4** Files under ~500 lines (split if larger)

**Common violation**: Nested ternaries that are hard to read.

### 10. Security

- [ ] **10.1** No secrets/credentials in code or committed files
- [ ] **10.2** Sensitive data not leaked to frontend (check SSR props)
- [ ] **10.3** RBAC checks applied before data access
- [ ] **10.4** User input validated at API boundary

**Common violation**: Accidentally committing API keys or tokens.

### 11. Testing

- [ ] **11.1** New functionality has corresponding tests
- [ ] **11.2** Error paths tested, not just happy paths
- [ ] **11.3** Integration tests for DB operations with constraints/upserts

**Common violation**: Testing only the happy path.

---

## Quick Validation Commands

```bash
# Type check
npm run tsc

# Lint
npm run lint

# Run tests
npm run test

# Check for any console.log left
grep -r "console.log" bff/src copilot/src --include="*.ts" --include="*.tsx"

# Check for any 'any' types
grep -r ": any" bff/src copilot/src --include="*.ts" --include="*.tsx"
```

---

## Severity Guide

When reviewing, classify issues by impact:

| Severity     | Description                     | Examples                                             |
| ------------ | ------------------------------- | ---------------------------------------------------- |
| **Critical** | Blocks merge, breaks production | Security breach, data loss, silent failures          |
| **Major**    | Must fix before merge           | Missing error handling, tenant leakage, broken logic |
| **Minor**    | Should fix, not blocking        | Missing tests, code style, naming                    |
| **Nitpick**  | Optional improvement            | Formatting, minor refactoring suggestions            |

---

## References

- Full coding standards: `docs/code-standards.md`
- Project guidelines: `AGENTS.md`
- Architecture docs: `docs/architecture.md`
