# Code Standards & Best Practices

This document defines the coding standards and best practices for this codebase. It should be referenced by:

- **Coding agents** during implementation to ensure code adheres to standards
- **Code review agents** (`agents/code-review.md`) to validate compliance
- **Developers** as a reference for consistent patterns

> **Note**: This document complements but does not replace project-specific rules in `.cursor/rules`, `AGENTS.md`, and subproject-specific rules files.

## Table of Contents

1. [Architecture & Separation of Concerns](#architecture--separation-of-concerns)
2. [Type Safety & TypeScript](#type-safety--typescript)
3. [Testing Requirements](#testing-requirements)
4. [Security Standards](#security-standards)
5. [Performance Guidelines](#performance-guidelines)
6. [Code Quality & Maintainability](#code-quality--maintainability)
7. [Naming Conventions](#naming-conventions)
8. [Error Handling & Logging](#error-handling--logging)
9. [Database & Migrations](#database--migrations)
10. [Frontend-Specific Standards](#frontend-specific-standards)
11. [Backend-Specific Standards](#backend-specific-standards)
12. [AI Code Quality & Complexity](#ai-code-quality--complexity)
13. [Code Cleanliness](#code-cleanliness)

---

## Architecture & Separation of Concerns

### Layer Separation

- **Routers/Controllers**: Must be thin - only handle HTTP request/response, validation, and delegation to services
- **Services**: Contain all business logic and orchestration
- **Repositories**: Only handle database operations (queries, transactions) - NO business logic, NO queue/Redis operations
- **Orchestration**: BullMQ flows, jobs, and queue operations belong in `src/orchestration/`, not repositories

### ✅ Good Examples

```typescript
// Router - thin, delegates to service
router.get("/reports", async (req, res) => {
  const reports = await service.getAll();
  res.json({ data: reports });
});

// Service - contains business logic
class ReportService {
  async getAll() {
    const reports = await repo.getAll();
    const jobStates = await this.loadJobStates(reports.map((r) => r.id));
    return this.enrichWithJobStates(reports, jobStates);
  }
}

// Repository - only DB operations
class ReportRepository {
  async getAll() {
    return db.select().from(reports);
  }
}
```

### ❌ Anti-Patterns

- Business logic in routers
- Queue/Redis operations in repositories
- Database queries in services when they should be in repositories
- Circular dependencies (use dependency injection or service layer to break cycles)

---

## Type Safety & TypeScript

### Type Requirements

- **No `any` types** - Use explicit types or `unknown` with type guards
- **Prefer shared types** - Use types from `@shared/types` for cross-project consistency
- **Use enums, not strings** - For finite value sets (status, jurisdiction, etc.), use TypeScript enums from `@shared/enums`
- **Named exports** - Complex inline types should be extracted as named interfaces/types
- **Type guards** - Use proper type guards for runtime validation (zod schemas, type predicates)
- **Avoid unnecessary type casting** - Type casting (`as`) should only be used in exceptional circumstances with a comment explaining why it's necessary. Prefer fixing types at their source or using type guards instead of casting.

### ✅ Good Examples

```typescript
// Use shared types
import { OverlapsAnalysis, ReportStatus } from "@shared/types";

// Named interface for complex types
interface PromptDisplayData {
  label: string;
  status: PromptJobStatus;
  findings: string | null;
}

// Type guard
function isCompleted(status: string): status is ReportStatus.COMPLETED {
  return status === ReportStatus.COMPLETED;
}
```

### ❌ Anti-Patterns

```typescript
// ❌ Using any
const data: any = await fetchData();

// ❌ Complex inline types
const process = (data: { id: string; metadata: { version: number; label: string } }) => {};

// ❌ Missing type guards
if (typeof data.status === 'string') { // Should use proper type guard
}

// ❌ Unnecessary type casting without explanation
status: q.status as MergerFormQuestionStatusEnum | null | undefined,
// TypeScript already handles this assignment correctly - cast is redundant

// ❌ Type casting to work around type errors instead of fixing types
const result = apiCall() as ExpectedType; // Should fix the API return type instead
```

### Type Casting Guidelines

Type casting (`as`) should only be used in exceptional circumstances and must include a comment explaining why. Prefer fixing types at their source or using type guards instead of casting. Remember that optional properties (`prop?`) already accept `undefined`, and TypeScript's structural typing often makes casts unnecessary.

---

## Testing Requirements

### Test Coverage Expectations

- **New features**: Must include tests for happy path, error cases, and edge cases
- **Critical paths**: RBAC checks, tenant isolation, data validation
- **API routes**: Test request/response, error handling, authentication
- **Services**: Unit tests for business logic
- **Repositories**: Integration tests with database
- **Components**: Unit tests with Vitest/RTL, accessibility tests

### Repository & Database Testing

**Prefer integration tests with testcontainers** for repository and database testing. Integration tests prove the queries actually work against a real database.

#### When to Use Integration Tests (Preferred)

Use integration tests for anything that needs to verify actual database behavior:

- **Validation & constraints** - unique indexes, FK violations, CHECK constraints
- **Drizzle/ORM behavior** - `onConflictDoUpdate`, `onConflictDoNothing`, upserts
- **Transactions** - atomicity, rollback behavior
- **Complex queries** - joins, aggregations, CTEs
- **Complex workflows** - multi-step operations that touch multiple tables

#### ✅ Good - Integration Test

```typescript
// Tests actual database behavior
describe('MergerFormPrecedentRepo.upsertPrecedent', () => {
  it('should update existing precedent when upserting with same id', async () => {
    // First insert
    await MergerFormPrecedentRepo.upsertPrecedent({ id: precedentId, ... });

    // Second upsert with same ID - should UPDATE, not fail
    await MergerFormPrecedentRepo.upsertPrecedent({ id: precedentId, ... });

    // Verify only 1 row exists (proves upsert works at SQL level)
    const rows = await db.select().from(precedents).where(eq(precedents.id, precedentId));
    expect(rows).toHaveLength(1);
  });
});
```

#### When Unit Tests with Light Mocking Are Acceptable

Unit tests with mocks can be used pragmatically for simple verification where integration tests would be overkill:

- **Verifying correct table usage** - e.g., confirming code inserts to `attachment_content` not `report_files`
- **Testing mapping/transformation logic** - pure functions that don't need DB
- **Testing error handling paths** - when you need to simulate specific error conditions

```typescript
// Acceptable: Light mock to verify correct table is used
it("should use attachment_content table, NOT report_files", async () => {
  await mergerFormRepo.upsertAttachment(reportId, documentText);
  expect(lastInsertTable).toBe(attachmentContent);
  expect(lastInsertTable).not.toBe(reportFiles);
});
```

**Key principle**: If you need to verify SQL-level behavior (constraints, upserts, transactions), use integration tests. Mocked tests cannot prove SQL correctness.

### Test Organization

- **Location**: Tests live near code in `__tests__` directories
- **Naming**: `*.test.ts` or `*.spec.ts`
- **Structure**: Use `describe`/`it` blocks with descriptive names that explain behavior

### ✅ Good Examples

```typescript
describe("ReportService.getAll()", () => {
  it("should return reports with job states", async () => {
    // Test implementation
  });

  it("should handle missing job states gracefully", async () => {
    // Error case
  });

  it("should enforce tenant isolation", async () => {
    // Security check
  });
});
```

### Missing Test Indicators

- New API endpoint without route test
- New service method without unit test
- New component without component test
- RBAC logic without authorization test
- Database query without integration test

---

## Security Standards

### Authentication & Authorization

- **All endpoints** must have appropriate auth middleware
- **RBAC checks** must be applied before data access, not after
- **Tenant isolation** must be enforced on all queries
- **IDOR prevention** - IDs in URLs/params must be validated against user's permissions

### Tenant Filtering Pattern

The established pattern uses **in-memory filtering** with `defaultOrg` fallback handling. This pattern is consistent across all report repositories.

#### ✅ Current Pattern - In-Memory Filtering

```typescript
// Established pattern across all repos (rfi, csi, fdi, overlaps, merger-form, etc.)
async getAll(projectId?: string, organisationIds?: string[]): Promise<Report[]> {
  const results = await db.query.reports.findMany({
    where: eq(reports.reportType, ReportType.MY_TYPE),
  });

  const defaultOrg = rbacService.getDefaultOrganisationId();
  let mapped = results.map((row) => this._mapReport(row));

  if (organisationIds && organisationIds.length > 0) {
    mapped = mapped.filter((row) => {
      const effectiveOrg = row.organisationId ?? defaultOrg;
      return !effectiveOrg || organisationIds.includes(effectiveOrg);
    });
  }
  return mapped;
}
```

**Why this pattern?** The `defaultOrg` fallback logic handles legacy records and edge cases that are complex to express in SQL WHERE clauses. For consistency, follow this established pattern.

> **Note**: SQL-level filtering (using `inArray()` in WHERE clause) is theoretically cleaner for performance and is acceptable if implemented consistently. However, it should not be introduced piecemeal - any migration to SQL filtering should be a deliberate codebase-wide change.

### Tenant Identifier Resolution

The established pattern resolves `organisationId` at the **router/service layer**, not in validators. Validators validate user input; routers resolve tenant context.

#### ✅ Current Pattern - Router-Level Resolution

```typescript
// Validator - validates user input, does NOT include organisationId
export const createMergerFormSchema = z.object({
  name: z.string().min(1),
  fileIds: z.array(z.string().uuid()),
  projectSettings: projectSettingsSchema,
  // organisationId is resolved at router level, not validated here
});

// Router - resolves organisationId from user context
router.post("/", validate(createMergerFormSchema), async (req, res) => {
  const user = req.user!;
  const organisationId = rbacService.resolveOrganisationId(
    user,
    req.body.organisationId,
  );
  // ... pass organisationId to service
});
```

**Why this pattern?** The organisationId is derived from the authenticated user's context and permissions, not from untrusted client input. This ensures tenant scoping is always correct.

### Ownership Validation

- **Validate ownership** - confirm files/resources belong to the caller's organisation
- **Project ownership checks** - when using existing projects, verify user has access

### Input Validation

- **All user input** must be validated at the boundary using zod schemas or express-validator
- **Never trust client data** - validate and sanitize all inputs
- **Type coercion** - Use proper type conversion, not implicit coercion

### Data Exposure Prevention

- **No sensitive data** in SSR page props or initial state
- **Error messages** must not expose stack traces, SQL queries, or file paths
- **PII** must not be logged or must be properly redacted
- **API responses** must not leak internal IDs or other users' data

### ✅ Good Examples

```typescript
// Input validation with zod
const schema = z.object({
  reportId: z.string().uuid(),
  userId: z.string().uuid(),
});

// Tenant isolation in query
const reports = await db
  .select()
  .from(reports)
  .where(eq(reports.organisationId, user.organisationId)); // ✅ Tenant check

// RBAC check before access
if (!(await canAccessReport(user, reportId))) {
  throw new ForbiddenError();
}
```

### ❌ Anti-Patterns

```typescript
// ❌ No tenant isolation
const reports = await db.select().from(reports); // Missing WHERE clause

// ❌ RBAC check after data fetch
const report = await repo.getById(id);
if (report.userId !== user.id) throw Error(); // Too late!

// ❌ Trusting client input
const reportId = req.params.id; // Should validate!
await repo.delete(reportId);
```

### OWASP Attack Prevention

Reference guide for common web vulnerabilities. See [OWASP Top 10](https://owasp.org/Top10/) for full details.

#### SQL/NoSQL Injection

**Never** interpolate user input into queries. Always use parameterized queries.

```typescript
// ✅ Safe - parameterized query (Drizzle ORM)
const users = await db.select().from(users).where(eq(users.id, userId));

// ✅ Safe - prepared statement
const result = await db.execute(sql`SELECT * FROM users WHERE id = ${userId}`);

// ❌ Vulnerable - string interpolation
const result = await db.execute(`SELECT * FROM users WHERE id = '${userId}'`);

// ❌ Vulnerable - dynamic column names
const result = await db.execute(`SELECT * FROM users ORDER BY ${sortColumn}`);
```

#### Cross-Site Scripting (XSS)

React escapes by default, but watch for these patterns:

```typescript
// ✅ Safe - React auto-escapes
return <div>{userInput}</div>;

// ❌ Vulnerable - dangerouslySetInnerHTML
return <div dangerouslySetInnerHTML={{ __html: userInput }} />;

// ❌ Vulnerable - href with user input (javascript: URLs)
return <a href={userProvidedUrl}>Link</a>;

// ✅ Safe - validate URL protocol
const safeUrl = userProvidedUrl.startsWith('https://') ? userProvidedUrl : '#';
return <a href={safeUrl}>Link</a>;
```

**SSR considerations** - sanitize data before serializing to page props:

```typescript
// ❌ Vulnerable - raw HTML in SSR props
export async function getServerSideProps() {
  return { props: { content: rawHtmlFromDb } }; // Can execute on hydration
}

// ✅ Safe - sanitize or escape
import DOMPurify from "isomorphic-dompurify";
export async function getServerSideProps() {
  return { props: { content: DOMPurify.sanitize(rawHtmlFromDb) } };
}
```

#### Cross-Site Request Forgery (CSRF)

- **API routes** - Use CSRF tokens for state-changing operations from browser
- **SameSite cookies** - Set `SameSite=Strict` or `SameSite=Lax` on auth cookies
- **Origin validation** - Verify `Origin` or `Referer` headers on sensitive endpoints

#### Server-Side Request Forgery (SSRF)

Prevent attackers from making requests to internal services:

```typescript
// ❌ Vulnerable - user controls URL
const response = await fetch(userProvidedUrl);

// ✅ Safe - allowlist domains
const ALLOWED_DOMAINS = ["api.example.com", "cdn.example.com"];
const url = new URL(userProvidedUrl);
if (!ALLOWED_DOMAINS.includes(url.hostname)) {
  throw new ForbiddenError("Domain not allowed");
}

// ✅ Safe - block internal IPs
const blockedPatterns = [/^localhost/, /^127\./, /^10\./, /^192\.168\./];
if (blockedPatterns.some((p) => p.test(url.hostname))) {
  throw new ForbiddenError("Internal addresses not allowed");
}
```

#### Command Injection

Avoid shell execution with user input:

```typescript
// ❌ Vulnerable - shell execution with user input
exec(`convert ${userFilename} output.png`);

// ✅ Safe - use execFile with argument array (no shell)
execFile("convert", [userFilename, "output.png"]);

// ✅ Safe - sanitize filename
const safeFilename = path.basename(userFilename).replace(/[^a-zA-Z0-9.-]/g, "");
```

#### Insecure Deserialization

- **Never** use `eval()`, `Function()`, or `vm.runInContext()` with user input
- **Validate JSON** structure with zod schemas before processing
- **Avoid** deserializing complex objects from untrusted sources

```typescript
// ❌ Vulnerable
const config = eval(userInput);

// ❌ Vulnerable - arbitrary object construction
const obj = JSON.parse(userInput);
obj.constructor.prototype.polluted = true; // Prototype pollution

// ✅ Safe - validate with schema
const configSchema = z.object({ key: z.string(), value: z.number() });
const config = configSchema.parse(JSON.parse(userInput));
```

#### Security Headers

Ensure these headers are set (typically in middleware or Next.js config):

| Header                      | Value                  | Purpose                |
| --------------------------- | ---------------------- | ---------------------- |
| `Content-Security-Policy`   | Restrict sources       | Prevent XSS, injection |
| `X-Content-Type-Options`    | `nosniff`              | Prevent MIME sniffing  |
| `X-Frame-Options`           | `DENY` or `SAMEORIGIN` | Prevent clickjacking   |
| `Strict-Transport-Security` | `max-age=...`          | Force HTTPS            |
| `X-XSS-Protection`          | `1; mode=block`        | Legacy XSS filter      |

---

## Performance Guidelines

### Database Queries

- **Avoid N+1 queries** - Use batch loading with `IN` clauses or joins
- **Index usage** - Ensure queries use appropriate indexes
- **Query optimization** - Review slow queries, use EXPLAIN ANALYZE

### Caching

- **React Query staleTime** - Use `STALE_RESEARCH_TIME` constant consistently
- **Cache invalidation** - Properly invalidate caches on mutations
- **Redis usage** - Use for job state caching, not business logic storage

### Frontend Performance

- **Code splitting** - Use dynamic imports for large components
- **Image optimization** - Use Next.js Image component
- **Bundle size** - Avoid unnecessary dependencies

### ✅ Good Examples

```typescript
// Batch loading instead of N+1
const reportIds = reports.map((r) => r.id);
const promptResults = await repo.loadPromptResultsBatch(reportIds); // ✅ Single query

// Proper cache invalidation
queryClient.invalidateQueries({ queryKey: [reportQueryKey] });
```

### ❌ Anti-Patterns

```typescript
// ❌ N+1 query pattern
for (const report of reports) {
  const results = await repo.loadPromptResults(report.id); // Bad!
}

// ❌ Missing cache invalidation
await deleteReport(id);
// Should invalidate queries here!
```

---

## Code Quality & Maintainability

### YAGNI (You Ain't Gonna Need It)

- **Avoid premature abstraction** - Don't create generic solutions, wrappers, or abstractions until you have multiple concrete use cases
- **Prefer explicit over generic** - Use specific method names and implementations rather than generic ones until patterns emerge
- **No unnecessary layers** - Avoid creating thin wrapper methods that just delegate to other methods without adding value
- **Question abstractions** - If an abstraction doesn't clearly simplify or enable reuse, prefer direct implementation

**Note**: YAGNI applies to **new abstractions and wrappers**, not to established architectural patterns. The Router → Service → Repository separation is an architectural decision, not a "wrapper" to avoid.

### Keep Surface Area Tight

- **Minimize exposed methods** - Only expose what's actually needed by callers
- **Avoid unnecessary indirection** - Don't add extra delegation layers (e.g., repo method that just calls service method with same signature)
- **Small, focused changes** - Keep the scope of changes minimal—don't refactor unrelated code "while you're at it"
- **Remove unused code** - Delete methods, classes, or exports that aren't being used

**Note**: This doesn't mean avoiding proper layer separation. Router → Service → Repository is correct architecture. Avoid adding **extra** methods that don't add value (e.g., `repo.method()` that just calls `service.method()` with identical parameters).

### Balancing YAGNI, DRY, and Architecture

These principles work together, not in conflict:

- **YAGNI vs DRY**: DRY applies when you have **actual duplication** (2+ uses), not theoretical future duplication. Extract shared logic when you see real repetition, not "just in case."
- **YAGNI vs Layer Separation**: Router → Service → Repository is an architectural pattern, not a "wrapper." YAGNI applies to **additional** wrappers beyond this pattern (e.g., don't add `repo.assembleSor()` that just calls `service.assembleSorForMergerForm()`).
- **Tight Surface Area vs Thin Layers**: Thin layers mean each layer has a clear responsibility. Tight surface area means don't expose methods you don't need. Both can coexist—maintain proper separation while minimizing unnecessary methods.

**Decision Framework**:

1. **Established pattern?** (Router → Service → Repository) → Follow it
2. **Actual duplication?** (Same code in 2+ places) → Extract (DRY)
3. **Theoretical future need?** → Don't abstract yet (YAGNI)
4. **Thin wrapper with no value?** → Remove it (Tight surface area)

### DRY (Don't Repeat Yourself)

- **Reuse existing utilities** - Check for existing functions/components before creating new ones
- **Extract common logic** - Create shared utilities for repeated patterns
- **Consolidate similar code** - Merge duplicate implementations

### Single Responsibility

- **One purpose per function/class** - Functions should do one thing well
- **Focused components** - Components should have a single responsibility
- **Clear boundaries** - Each layer should have clear responsibilities

### Code Organization

- **Feature-based structure** - Group related files together
- **Consistent patterns** - Follow existing patterns in the codebase
- **Clear imports** - Use absolute imports with `@/` prefix

### ✅ Good Examples

```typescript
// Reusable utility function
export const formatTime = (ms: number): string => {
  // Implementation
};

// Extracted component
export const StatusCell = ({ status, report }: StatusCellProps) => {
  // Single responsibility
};

// Direct service call (no unnecessary wrapper)
const sor = await statementOfRecordService.assembleFullSorForMergerForm(reportId);

// Specific method name (not generic)
async assembleFullSorForMergerForm(reportId: string) {
  // Clear, explicit purpose
}
```

### ❌ Anti-Patterns

```typescript
// ❌ Duplicate logic
const formatTime1 = (ms: number) => {
  /* ... */
};
const formatTime2 = (ms: number) => {
  /* ... */
}; // Should reuse!

// ❌ God component
const MegaComponent = () => {
  // Handles everything - should be split
};

// ❌ Unnecessary wrapper (adds no value) - violates tight surface area
class Repo {
  async assembleFullSor(id: string) {
    return await service.assembleFullSorForMergerForm(id); // Just delegates, no transformation
  }
}
// ✅ Better: Call service directly
const sor = await statementOfRecordService.assembleFullSorForMergerForm(reportId);

// ❌ Premature abstraction - violates YAGNI
async assembleSor<T>(id: string, type: SorType): Promise<T> {
  // Generic when only one use case exists
}
// ✅ Better: Specific method until patterns emerge
async assembleFullSorForMergerForm(reportId: string): Promise<MaterialCollection> {
  // Clear, explicit purpose
}

// ✅ Proper layer separation (not a "wrapper")
// Router → Service → Repository is correct architecture
router.get('/reports/:id', async (req, res) => {
  const report = await reportService.getById(req.params.id); // ✅ Service layer
  res.json({ data: report });
});

class ReportService {
  async getById(id: string) {
    const report = await reportRepo.getById(id); // ✅ Repository layer
    return this.enrichWithJobStates(report); // ✅ Business logic in service
  }
}
```

---

## Code Style Patterns

### Avoid Nested Ternaries

Nested ternaries are hard to read and maintain. Use if/else or early returns instead:

```typescript
// ❌ Bad - nested ternary
const status = isLoading
  ? "loading"
  : hasError
    ? "error"
    : isComplete
      ? "done"
      : "pending";

// ✅ Good - if/else or early returns
const getStatus = () => {
  if (isLoading) return "loading";
  if (hasError) return "error";
  if (isComplete) return "done";
  return "pending";
};

// ✅ Good - single ternary is fine
const label = isActive ? "Active" : "Inactive";
```

### Static Arrays and Objects

Define static data outside of render functions to avoid unnecessary re-creation:

```typescript
// ✅ Good - defined once outside component
const STATUS_OPTIONS = ['pending', 'active', 'completed'] as const;
const COLUMN_WIDTHS = { name: 200, status: 100, date: 150 };

const MyComponent = () => {
  // Uses static reference
  return <Select options={STATUS_OPTIONS} />;
};

// ❌ Bad - recreated on every render
const MyComponent = () => {
  const options = ['pending', 'active', 'completed']; // New array every render
  return <Select options={options} />;
};
```

---

## Naming Conventions

### Functions & Variables

- **camelCase** for functions, variables, and file names
- **Descriptive names** - Names should clearly indicate purpose
- **Avoid abbreviations** - Use full words unless abbreviation is standard

### Components & Types

- **PascalCase** for React components and TypeScript interfaces
- **Component names** should match file names
- **Interface names** should be descriptive (avoid `Props`, prefer `ComponentNameProps`)

### Files & Directories

- **kebab-case** for file paths and CSS classes
- **Feature-based** organization in directories
- **Consistent naming** across similar files

### ✅ Good Examples

```typescript
// Functions
const loadPromptJobStates = async () => {};
const formatReportName = (report: Report) => {};

// Components
export const OverlapsProgressBar = () => {};
interface OverlapsProgressBarProps {}

// Files
overlaps - progress - bar.tsx;
load - prompt - job - states.ts;
```

---

## Error Handling & Logging

### Error Handling

- **Proper error types** - Use appropriate error classes (NotFoundError, ValidationError, etc.)
- **Error boundaries** - Frontend components should have error boundaries
- **Graceful degradation** - Handle errors without crashing the application
- **User-friendly messages** - Errors shown to users should be clear and actionable

### Throw vs Return Null

Services and job processors should **throw on errors**, not return null:

- **Throw errors** for failures, unexpected conditions, validation errors
- **Return null** only for "not found" scenarios (and document this behavior)
- **Include context** in thrown errors for debugging

```typescript
// ✅ Good - throw on failure
async getById(id: string): Promise<Report> {
  const report = await repo.findById(id);
  if (!report) {
    throw new NotFoundError(`Report ${id} not found`);
  }
  return report;
}

// ✅ Good - return null for "not found" (documented)
async findById(id: string): Promise<Report | null> {
  return db.select().from(reports).where(eq(reports.id, id)).get();
}

// ❌ Bad - returning null on failure
async processJob(data: JobData): Promise<Result | null> {
  try {
    return await doWork(data);
  } catch (error) {
    return null; // Silent failure! Job appears successful
  }
}
```

### Catch Block Requirements

- **Never have empty catch blocks** - Always log or handle the error
- **Log before re-throwing** - Include context for debugging
- **Don't swallow errors** - If you catch, either handle fully or re-throw

```typescript
// ✅ Good - log with context, then re-throw
try {
  await processDocument(docId);
} catch (error) {
  logger.error("Failed to process document", { docId, error });
  throw error;
}

// ✅ Good - fully handle the error
try {
  await sendNotification(userId);
} catch (error) {
  logger.warn("Notification failed, continuing", { userId, error });
  // Intentionally swallowed - notifications are best-effort
}

// ❌ Bad - empty catch
try {
  await riskyOperation();
} catch (error) {
  // Silent failure!
}

// ❌ Bad - catch without logging
try {
  await riskyOperation();
} catch (error) {
  throw new Error("Operation failed"); // Lost original error context
}
```

### Logging

- **Structured logging** - Use logger with appropriate levels (info, warn, error)
- **Context in logs** - Include relevant context (IDs, user info, operation)
- **No sensitive data** - Never log passwords, tokens, or PII
- **Consistent patterns** - Follow existing logging patterns

### ✅ Good Examples

```typescript
// Proper error handling
try {
  const report = await service.getById(id);
} catch (error) {
  if (error instanceof NotFoundError) {
    return res.status(404).json({ error: "Report not found" });
  }
  logger.error("Failed to fetch report", { reportId: id, error });
  throw error;
}

// Structured logging
logger.info("Flow created", {
  reportId,
  jobId,
  correlationId,
  selectedPrompts,
  promptCount,
});
```

---

## Database & Migrations

### Required Table Fields

All tables should include standard audit fields:

```typescript
// ✅ Required fields for all tables
export const myTable = pgTable("my_table", {
  id: text("id")
    .primaryKey()
    .$defaultFn(() => crypto.randomUUID()),
  // ... business fields ...
  createdAt: timestamp("created_at").notNull().defaultNow(),
  updatedAt: timestamp("updated_at").$onUpdate(() => new Date()),
});
```

- **`created_at`** - NOT NULL, defaults to now() - when the record was created
- **`updated_at`** - Nullable, auto-updated on changes - when last modified

### Soft Deletes

For tables that support soft deletion:

```typescript
export const myTable = pgTable("my_table", {
  // ... other fields ...
  deletedAt: timestamp("deleted_at"), // NULL = not deleted
});
```

**Critical**: All queries on soft-deletable tables MUST filter for non-deleted records:

```typescript
// ✅ Good - always filter soft deletes
async getAll(): Promise<MyRecord[]> {
  return db.select().from(myTable).where(isNull(myTable.deletedAt));
}

async getById(id: string): Promise<MyRecord | null> {
  return db.select().from(myTable).where(
    and(eq(myTable.id, id), isNull(myTable.deletedAt))
  ).get();
}

// ❌ Bad - leaks deleted records
async getAll(): Promise<MyRecord[]> {
  return db.select().from(myTable); // Missing deletedAt filter!
}
```

**Tip**: Create repository base methods that include the soft delete filter by default.

### Multi-Tenancy Scoping Patterns

When using nullable foreign keys for hierarchical scoping (e.g., `report_id`, `organisation_id`), follow these rules:

- **"Global" means ALL scope fields are NULL** - A record is only global when every scoping FK is NULL, not just one
- **Document scope semantics** - Comment what each combination of NULL/non-NULL means
- **Query accordingly** - Use `AND` conditions, not single column checks

#### ✅ Good Examples

```typescript
// Global = both reportId AND organisationId are NULL
async listGlobalPrecedents() {
  return db.select().from(precedents).where(
    and(isNull(precedents.reportId), isNull(precedents.organisationId))
  );
}

// Org-scoped = reportId is NULL, organisationId is set
// Report-scoped = both are set
```

#### ❌ Anti-Patterns

```typescript
// ❌ Wrong - leaks org-scoped records to global queries
async listGlobalPrecedents() {
  return db.select().from(precedents).where(isNull(precedents.reportId));
  // Missing: isNull(precedents.organisationId)
}
```

### Migration Safety

- **Idempotent migrations** - Migrations should be safe to run multiple times
- **Backward compatibility** - Consider rollback strategies
- **Default values** - Provide safe defaults for new columns
- **Data backfill** - Back-fill data where necessary

### Query Safety

- **Parameterized queries** - Always use parameterized queries (Drizzle handles this)
- **Transaction usage** - Use transactions for multi-step operations that must succeed or fail together
- **Referential integrity** - Maintain foreign key constraints

### Foreign Key Deletion Strategies

Choose the right `onDelete` behavior based on the relationship:

- **CASCADE** - Child records should be deleted when parent is deleted (e.g., report → answers)
- **SET NULL** - Child should survive with NULL reference (e.g., extract → source document)
- **NO ACTION** - Prevent deletion if children exist (e.g., organisation → users)

```typescript
// CASCADE: answers are deleted when report is deleted
reportId: text("report_id").references(() => reports.id, {
  onDelete: "cascade",
});

// SET NULL: extracts survive when source document is deleted/replaced
sourceDocumentId: text("source_document_id").references(() => files.id, {
  onDelete: "set null",
});
```

### NULL Handling in Queries

When querying with optional parameters that map to nullable columns:

- **Use `isNull()` when parameter is omitted** - Don't skip the condition entirely
- **Document the semantics** - NULL often has specific meaning (e.g., "section-level" vs "question-level")

```typescript
// When questionId is omitted, we want records WHERE question_id IS NULL
async getBySectionAndQuestion(reportId: string, sectionId: string, questionId?: string) {
  return db.select().from(answers).where(
    and(
      eq(answers.reportId, reportId),
      eq(answers.sectionId, sectionId),
      questionId
        ? eq(answers.questionId, questionId)  // Match specific question
        : isNull(answers.questionId)          // Match section-level (NULL)
    )
  );
}
```

### ✅ Good Examples

```typescript
// Safe migration with defaults
export const addStatusColumn = sql`
  ALTER TABLE reports
  ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'PENDING'
`;

// Transaction usage
await db.transaction(async (tx) => {
  await tx.insert(reports).values(data);
  await tx.insert(promptResults).values(results);
});
```

---

## Frontend-Specific Standards

### React Components

- **Functional components** - Use functional components with hooks
- **TypeScript interfaces** - Define prop interfaces explicitly
- **Client/Server boundaries** - Mark client components with `'use client'`
- **Server components** - Prefer server components when possible

### State Management

- **React Query** - Use Tanstack Query for server state
- **React Hook Form** - Use for form state management
- **Local state** - Use `useState` for component-local state
- **Avoid global state** - Prefer prop drilling or React Query for shared state

### Styling

- **Tailwind CSS** - Use utility classes, not custom CSS
- **Consistent spacing** - Use Tailwind spacing scale
- **Responsive design** - Use Tailwind responsive prefixes
- **Design system** - Follow existing color palette and component patterns

### Data Fetching

- **Consistent staleTime** - Use `STALE_RESEARCH_TIME` constant
- **Loading states** - Always handle loading and error states
- **Cache invalidation** - Invalidate queries on mutations

### ✅ Good Examples

```typescript
// Proper hook usage
export const useOverlapsAnalysisById = (id: string) => {
  return useQuery({
    queryKey: [overlapsQueryKey, id],
    queryFn: () => api.fetchById(id),
    staleTime: STALE_RESEARCH_TIME, // ✅ Consistent constant
    refetchInterval: getReportPollingInterval,
  });
};

// Component with proper types
interface OverlapsProgressBarProps {
  promptJobStates?: Record<string, PromptJobStatus>;
  reportStatus: ReportStatus;
}

export const OverlapsProgressBar: FC<OverlapsProgressBarProps> = ({
  promptJobStates,
  reportStatus,
}) => {
  // Implementation
};
```

---

## Backend-Specific Standards

### Express Routers

- **Thin routers** - Routers should only handle HTTP concerns (request parsing, response formatting)
- **Delegation** - Delegate business logic to services or orchestrators
- **Error handling** - Use error middleware for consistent error responses
- **Validation** - Validate requests before processing

#### Why Thin Routers Matter

Thick routers that contain business logic become:

- **Hard to test** - HTTP layer is mixed with business logic
- **Hard to reuse** - Logic can't be called from other contexts (jobs, CLI, other routes)
- **Hard to maintain** - Multiple concerns tangled together

#### Extracting Orchestration Logic

When a router needs to coordinate multiple services/repos, extract to an **orchestrator** or **service**:

```typescript
// ❌ Thick router - hard to test, can't reuse logic
router.post("/", async (req, res) => {
  const user = req.user!;
  const organisationId = rbacService.resolveOrganisationId(
    user,
    req.body.organisationId,
  );

  // Project validation
  if (projectSettings.action === "USE_EXISTING") {
    const project = await ProjectRepo.findInfoById(
      projectSettings.projectId,
      user,
    );
    if (!project) throw new AccessDeniedError();
    if (
      project.organisationId !== organisationId &&
      !user.capabilities.isApplicationAdmin
    ) {
      throw new AccessDeniedError();
    }
  }

  // More business logic...
  const id = await service.create({ ...form, organisationId });
  res.json({ data: { id } });
});

// ✅ Thin router - delegates to orchestrator/service
router.post("/", validate(createSchema), async (req, res, next) => {
  try {
    const result = await reportOrchestrator.createReport(req.user!, req.body);
    res.json({ data: result });
  } catch (error) {
    next(error);
  }
});
```

> **Note**: Some existing routers contain orchestration logic. When modifying these, consider extracting complex logic to services/orchestrators. New routes should follow the thin router pattern.

### BullMQ & Jobs

- **Correlation IDs** - Include correlation IDs in job data and all related logs
- **Retry safety** - Ensure jobs are safe to retry (idempotent)
- **Error handling** - Proper error handling in job processors
- **Flow patterns** - Use flows for complex multi-step operations

### Job Processor Error Handling

Job processors must fail explicitly on errors - never return null or swallow exceptions:

```typescript
// ✅ Good - throw to fail the job (enables retry, visibility)
async processJob(job: Job<MyJobData>): Promise<Result> {
  const { reportId, correlationId } = job.data;

  try {
    const result = await doWork(job.data);
    if (!result) {
      throw new Error(`Failed to process report ${reportId}`);
    }
    return result;
  } catch (error) {
    logger.error('Job failed', { reportId, correlationId, error });
    throw error; // Re-throw to fail the job
  }
}

// ❌ Bad - returning null makes job appear successful
async processJob(job: Job<MyJobData>): Promise<Result | null> {
  try {
    return await doWork(job.data);
  } catch (error) {
    return null; // Job completes "successfully" with null - silent failure!
  }
}
```

### Job Data Mutation

Never mutate `job.data` directly - use `job.updateData()`:

```typescript
// ✅ Good - use updateData method
await job.updateData({
  ...job.data,
  processedAt: new Date().toISOString(),
});

// ❌ Bad - direct mutation can cause issues
job.data.processedAt = new Date().toISOString(); // Don't do this!
```

### Retry-Safe Repository Operations (Idempotency)

When implementing repository methods that will be called from queue jobs or could be retried:

- **Use upsert when unique constraints exist** - Plain inserts will crash on retry
- **Name methods accurately** - If the plan specifies `upsertAnswer`, implement `upsertAnswer`, not `create`
- **Handle functional indexes** - For COALESCE-based unique indexes that Drizzle can't target, use check-then-insert/update pattern

#### ✅ Good Examples

```typescript
// Retry-safe with unique constraint on (reportId, sectionId, questionId)
async upsertAnswer(data: AnswerInput): Promise<Answer> {
  const existing = await this.getBySectionAndQuestion(
    data.reportId, data.sectionId, data.questionId
  );

  if (existing) {
    return this.update(existing.id, data);
  }
  return this.insert(data);
}
```

#### ❌ Anti-Patterns

```typescript
// ❌ Will crash on retry due to unique constraint violation
async create(data: AnswerInput) {
  return db.insert(answers).values(data).returning();
}
```

### Batch Insert Idempotency

For batch inserts that might be retried (e.g., from queue jobs):

- **Use `onConflictDoNothing()`** when duplicates should be silently ignored
- **Use `onConflictDoUpdate()`** when duplicates should update existing records

```typescript
// Batch insert that's safe to retry - duplicates are ignored
async createMany(extracts: ExtractInput[]) {
  return db.insert(mergerFormExtracts)
    .values(extracts)
    .onConflictDoNothing() // Safe: won't fail if some already exist
    .returning();
}
```

### Transaction Safety

Wrap related operations in transactions to ensure atomicity:

- **Delete + Insert patterns** - Must be atomic (e.g., replacing dependencies)
- **Multi-table writes** - All succeed or all fail together

```typescript
// ✅ Atomic: dependencies never left in partial state
async replaceDependencies(answerId: string, extractIds: string[]) {
  await db.transaction(async (tx) => {
    await tx.delete(dependencies).where(eq(dependencies.answerId, answerId));
    if (extractIds.length > 0) {
      await tx.insert(dependencies).values(
        extractIds.map(extractId => ({ answerId, extractId }))
      );
    }
  });
}

// ❌ Non-atomic: if insert fails, deletes are committed
async replaceDependencies(answerId: string, extractIds: string[]) {
  await db.delete(dependencies).where(eq(dependencies.answerId, answerId));
  await db.insert(dependencies).values(...); // Failure leaves data inconsistent
}
```

### Services & Orchestration

- **Business logic** - All business logic belongs in services
- **Queue operations** - Queue/Redis operations belong in orchestration layer
- **Separation** - Keep services separate from repositories and orchestration

### ✅ Good Examples

```typescript
// Thin router
router.get("/reports/:id", async (req, res, next) => {
  try {
    const report = await reportService.getById(req.params.id);
    res.json({ data: report });
  } catch (error) {
    next(error);
  }
});

// Service with business logic
class ReportService {
  async getById(id: string) {
    const report = await repo.getById(id);
    const jobStates = await this.loadJobStates(id);
    return this.enrichWithJobStates(report, jobStates);
  }
}
```

---

## AI Code Quality & Complexity

### AI Slop Detection

Flag code that exhibits signs of AI-generated "slop":

- Overly verbose implementations that could be simplified
- Unnecessary abstractions (wrapper functions, factories) that add no value
- **Meaningless wrapper functions**: Functions that only delegate to another function with identical parameters and return types
- **Excessive intermediate variables**: Variables that are only used once and don't improve readability (e.g., `const x = result.prop; return x;`)
- Over-engineered solutions when simpler ones would suffice
- Excessive comments that restate code rather than explain why
- Overly generic code when domain-specific would be clearer
- Overly defensive patterns (excessive null checks, type guards) where not needed
- Copy-paste patterns that look templated without understanding context

### Cyclomatic Complexity

Use raw complexity as a starting point, then apply qualitative adjustments:

**Base Thresholds** (raw count):

- Complexity > 15: Must refactor before merge
- Complexity 10-15: Should be refactored
- Complexity ≤ 10: Acceptable

**Qualitative Adjustments** – Apply judgment based on these factors (can upgrade or downgrade severity):

- **Nesting depth**: Deep nesting (3+ levels) is worse than flat structures. A function with 12 flat branches is more readable than one with 8 branches at 4 levels deep.
- **Function length**: Long functions (>50 lines) compound complexity. Short functions (<30 lines) with clear structure are more acceptable at higher raw counts.
- **Code structure**: Early returns/guard clauses improve readability even with many branches. Tangled else-if chains are worse.
- **Helper function decomposition**: If complex logic is well-decomposed into helper functions, the parent function is more acceptable.
- **Comments & clarity**: Well-documented decision points (e.g., "// Priority 1: All failed") make branching more acceptable.

**Examples**:

- 12 branches, flat structure, clear comments, 35 lines → Acceptable
- 8 branches, 4 levels of nesting, no comments, 80 lines → Must refactor
- 15 branches, early returns, helper functions, well-documented → Acceptable or minor issue

**Complexity Calculation** – Count decision points:

- Each `if`, `else if`, `else` adds 1
- Each `switch` case adds 1
- Each loop (`for`, `while`, `do-while`) adds 1
- Each `catch` block adds 1
- Each `&&`, `||` operator in conditions adds 1
- Each ternary operator (`? :`) adds 1

**Refactoring Guidance**:

- Extract functions to break complex logic into smaller pieces
- Use early returns/guard clauses to reduce nesting
- Replace long if/else chains with lookup tables or maps
- Use strategy pattern for polymorphic behavior
- Remove unnecessary conditions and simplify logic

---

## Code Cleanliness

### Debug Artifacts

- **No console.log** - Remove all `console.log`, `console.debug` statements
- **No commented code** - Remove commented-out code blocks
- **No placeholders** - Remove placeholder text, test data, hardcoded IDs
- **No TODOs** - Remove `TODO`, `FIXME`, `HACK` comments (or track in tickets)

### Dead Code

- **Remove unused code** - Delete functions, classes, or exports that are never used
- **Remove unused files** - Delete files that aren't imported anywhere
- **Remove unused imports** - Clean up unused imports
- **Remove duplicate code** - Consolidate duplicate implementations

### Code Comments

- **Explain why, not what** - Comments should explain reasoning, not restate code
- **Keep comments updated** - Remove outdated comments
- **Documentation comments** - Use JSDoc for public APIs

### ✅ Good Examples

```typescript
// Good comment - explains why
// Set staleTime to 0 to ensure fresh data on every mount
// Without this, the global staleTime of 5 minutes would prevent refetching
staleTime: 0,

// Bad comment - restates what code does
// Set staleTime to 0
staleTime: 0,
```

### ❌ Anti-Patterns

```typescript
// ❌ Debug code
console.log("Debug:", data); // Remove before commit!

// ❌ Commented code
// const oldFunction = () => { ... }; // Should be deleted

// ❌ Placeholder
const testId = "test-123"; // Should use real data or env var

// ❌ TODO without ticket
// TODO: Fix this later // Should be in ticket tracker
```

---

## Quick Reference Checklist

When writing code, ensure:

### Architecture & Layers

- [ ] **Thin routers** - delegate business logic to services/orchestrators
- [ ] No queue/Redis operations in repositories - use orchestration layer
- [ ] **YAGNI** - No unnecessary abstractions, wrappers, or "future-proof" code
- [ ] **Tight surface area** - Minimize exposed methods, avoid unnecessary indirection

### Error Handling

- [ ] **Throw on errors, don't return null** - Services/processors should throw, not return null
- [ ] **Never empty catch blocks** - Always log errors with context
- [ ] Proper error handling and logging

### Database

- [ ] All inputs validated with zod schemas
- [ ] **Tenant filtering** - follow established in-memory pattern with `defaultOrg` fallback
- [ ] **organisationId resolved at router level** via `rbacService.resolveOrganisationId()`
- [ ] RBAC checks before data access
- [ ] **"Global" queries check ALL scope fields are NULL** (not just one)
- [ ] **Soft delete queries filter deletedAt IS NULL**
- [ ] **Tables have created_at/updated_at timestamps**
- [ ] **Upsert patterns** for operations with unique constraints (retry-safe)
- [ ] **onConflictDoNothing()** for batch inserts that might be retried
- [ ] **Transactions** for multi-step operations (delete+insert, multi-table writes)
- [ ] **Use enums** not strings for finite value sets

### BullMQ Jobs

- [ ] **Job processors throw on failure** - Never return null on errors
- [ ] **Don't mutate job.data** - Use job.updateData() instead
- [ ] **Include correlationId** in all job-related logs

### Types & Code Style

- [ ] No `any` types - use explicit types
- [ ] Proper TypeScript types and interfaces
- [ ] **No unnecessary type casting** - Casts only in exceptional circumstances with explanatory comments
- [ ] **No nested ternaries** - Use if/else or early returns
- [ ] **Static arrays as const** - Define outside render functions
- [ ] **Integration tests** for DB queries (constraints, upserts, transactions)

### Cleanup

- [ ] No debug artifacts (console.log, commented code, TODOs)
- [ ] Reuse existing utilities/components before creating new ones
- [ ] No N+1 queries - use batch loading
- [ ] Consistent use of constants (e.g., `STALE_RESEARCH_TIME`)

### Frontend

- [ ] Loading and error states handled in UI
- [ ] Cache invalidation on mutations

---

## References

- **AI Tool Rules**: `AGENTS.md`
- **Code Review Process**: `agents/code-review.md`
- **Architecture Documentation**: `docs/` (architecture.md, architectural-patterns.md, background-jobs.md, db-schema.md)
- **Frontend Rules**: `copilot/.cursor/rules` (optional extension)
- **Backend Rules**: `bff/.cursor/rules` (optional extension)
- **Root Rules**: `.cursor/rules`

---

**Last Updated**: Aligned with established codebase patterns (tenant filtering, organisationId resolution, testing approach, router thickness) - Dec 2024
