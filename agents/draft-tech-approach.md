# Draft Technical Approach Document — Agent Guide

This guide helps create technical approach documents that clearly lay out implementation choices, recommendations, and open questions. Use this when planning new features or major technical decisions.

## Purpose

Technical approach documents should:

- **Clarify decisions** before implementation begins
- **Compare alternatives** with clear recommendations
- **Identify unknowns** as explicit open questions
- **Minimize noise** — focus on decision-making content
- **Enable quick scanning** via TLDR and clear structure

## Document Structure

### 1. Header & TLDR

**Format**:

```markdown
# [Ticket Number] • [Feature Name] — Implementation Solutions & Approaches

## TLDR

**Key Decisions**:

- Decision 1 (brief rationale)
- Decision 2 (brief rationale)
- ...

**Open Questions**:

- Question 1 (what needs to be decided)
- Question 2 (what needs to be decided)
- ...

**Success Metrics**:

- Metric 1: target value
- Metric 2: target value
- ...
```

**Purpose**: Executives and busy stakeholders can understand key decisions and unknowns in 30 seconds.

**Guidelines**:

- Keep each bullet to one line
- Focus on **decisions made**, not implementation details
- List **genuine unknowns** that block decisions
- Include **measurable success criteria**

---

### 2. Table of Contents

**Format**:

```markdown
## Table of Contents

1. [Section Name](#anchor-link)
2. [Section Name](#anchor-link)
   ...
```

**Purpose**: Enable quick navigation for readers who want specific sections.

**Guidelines**:

- Use numbered list for easy reference
- Match section headers exactly (markdown auto-generates anchors)
- Keep it simple — don't nest subsections

---

### 3. Architecture Patterns to Reuse

**Purpose**: Identify existing patterns from the codebase that can be reused.

**Key Questions to Ask**:

- What similar features exist in the codebase?
- What patterns do they follow (database, queues, UI components)?
- Can we extend existing enums/tables/types?
- What infrastructure already exists (file processing, LLM calls, etc.)?

**Format**:

```markdown
## Architecture Patterns to Reuse

### 1. [Pattern Name] (from [Feature Name])

**Pattern**: Brief description of the pattern

**Implementation**:

- Specific steps to reuse it
- Code references if helpful
- Extensions needed

**Open Question**: [If pattern reuse raises questions]
```

**Guidelines**:

- Reference actual codebase patterns, not generic patterns
- Include specific file paths or examples
- Use ASCII diagrams for complex flows (see below)

---

### 3b. Base Class & Interface Contracts (CRITICAL)

**Purpose**: When extending abstract classes or implementing interfaces, explicitly document ALL inherited obligations to prevent implementation gaps.

**Why This Matters**: A common failure mode is documenting only NEW functionality while assuming implementers will "figure out" inherited methods. This leads to:

- Incorrect implementations (wrong table, wrong pattern)
- Bugs that only surface at runtime
- Time wasted debugging issues that should have been documented

**Key Questions to Ask**:

- What abstract class or interface are we extending?
- What abstract methods MUST be implemented?
- What is the CORRECT implementation pattern for each? (reference existing repos)
- Are there any methods with non-obvious semantics? (e.g., "attachment" means text content, not file IDs)

**Format**:

```markdown
## Base Class Contracts

### Extending `AbstractReportRepo`

When implementing a new report type repository, you MUST implement these abstract methods:

| Method                             | Purpose                                      | Implementation Pattern                                 | Reference                         |
| ---------------------------------- | -------------------------------------------- | ------------------------------------------------------ | --------------------------------- |
| `getById(id)`                      | Fetch report with related data               | Join report + type-specific table + files              | `document-review-repo.ts:45-80`   |
| `updateStatus(id, status)`         | Update report status                         | Update `reports` table, set `completedAt` if COMPLETED | `document-review-repo.ts:195-203` |
| `upsertAttachment(id, attachment)` | Store extracted document TEXT (not file IDs) | JSON.stringify to `attachment_content` table           | `document-review-repo.ts:205-216` |
| `getAttachmentContent(id)`         | Retrieve extracted document text             | JSON.parse from `attachment_content` table             | `document-review-repo.ts:218-229` |
| `upsertAnalysis(id, output)`       | Store analysis results                       | Varies by report type                                  | See specific repo                 |

**⚠️ Common Mistake**: `upsertAttachment` receives document TEXT content (output of `buildAttachment()`), NOT file IDs. Do NOT use `report_files` table for this.
```

**Guidelines**:

- **Always include a reference file** showing the correct implementation
- **Document non-obvious semantics** (like "attachment" meaning text, not files)
- **Include common mistakes** to prevent them
- **Use tables** for quick scanning of all required methods
- **Link to existing implementations** that can be copied

**Example - Bad vs Good**:

❌ **Bad**: "Extend `AbstractReportRepo` pattern for merger form repository"

✅ **Good**: Table showing all abstract methods with implementation patterns and file references (as above)

---

### 4. Comparison Tables

**Purpose**: Compare alternatives side-by-side to make decisions clear.

**When to Use Tables**:

- Multiple viable approaches exist
- Trade-offs need to be visible
- Decision criteria are clear

**Format**:

```markdown
## [Decision Topic]

| Approach | Pros               | Cons               | Recommendation         |
| -------- | ------------------ | ------------------ | ---------------------- |
| Option A | - Pro 1<br>- Pro 2 | - Con 1<br>- Con 2 | ✅ Recommended for MVP |
| Option B | - Pro 1            | - Con 1<br>- Con 2 | ❌ Too complex for v1  |
```

**Guidelines**:

- **Always include a recommendation column** — don't leave readers guessing
- Keep pros/cons concise (bullet points)
- Use ✅/❌ or **Recommended**/**Not Recommended** clearly
- If no clear winner, mark as "**Open Question**" and explain why

---

### 5. ASCII Diagrams

**Purpose**: Visualize flows, architectures, or data structures that are hard to describe in text.

**When to Use**:

- Complex workflows (e.g., BullMQ flows)
- Data transformations
- System interactions
- Database relationships (if not obvious from schema)

**Format**:

```markdown
**Flow Structure**:
```

Parent: [ParentJob]
├── Child: [ChildJob1] (parallel)
│ ├── [SubJob1]
│ └── [SubJob2]
├── Child: [ChildJob2] (after [dependency])
└── Child: [ChildJob3] (parallel)

```

```

**Guidelines**:

- Use simple tree structures (├──, └──, │)
- Indicate dependencies: `(after [X])`, `(parallel)`
- Keep it readable — don't overcomplicate
- Use code blocks (triple backticks) for formatting

---

### 6. Database Schema Design

**Purpose**: Show how data will be stored and related.

**Key Questions to Ask**:

- What entities need to be stored?
- What relationships exist?
- Do we need versioning/history?
- Can we reuse existing tables?
- What indexes are needed?

**Format**:

````markdown
## Database Schema Design

### Option A: [Approach Name] (Recommended)

**Schema**:

```sql
CREATE TABLE example (
  id TEXT PRIMARY KEY,
  ...
);
```
````

**Rationale**: Why this approach

**Open Questions**: [If schema design raises questions]

````

**Guidelines**:
- Show actual SQL (or Drizzle schema)
- Include indexes for performance-critical queries
- Explain normalization choices
- If multiple options exist, use comparison table format

---

### 7. Testing Strategy (CRITICAL)

**Purpose**: Identify what needs testing and HOW it should be tested during the planning phase — not as an afterthought.

**Why This Matters**: Many bugs occur because testing is planned too late or uses the wrong approach (mocking when integration tests are needed). Identifying test requirements during tech approach prevents:
- Critical paths tested only with mocks (masking real integration issues)
- Missing tenant isolation tests (security vulnerabilities)
- FK constraint issues only discovered in production
- Database behavior differences between mocks and real DB

**Key Questions to Ask**:
- What behaviors require a REAL database to test properly? (FK cascades, unique constraints, tenant isolation)
- What existing test patterns can we reuse?
- Where do we use test containers vs mocks?
- What are the critical paths that MUST have integration tests?

**Format**:
```markdown
## Testing Strategy

### Integration Tests (Use Test Containers — NO database mocking)

These tests MUST use the test container setup (`bff/src/__tests__/integration/`) with a real database:

| Test Area | Scenarios | Priority |
|-----------|-----------|----------|
| Tenant isolation | `getAll` filters by organisationIds, cross-tenant access rejected | Blocks merge |
| FK constraints | SET NULL/CASCADE behavior when referenced records deleted | Blocks merge |
| Unique constraints | NULL handling in unique indexes (e.g., COALESCE patterns) | Blocks merge |
| Repository queries | Complex joins, filters, pagination | Should have |

**Test Container Setup**: See `bff/src/__tests__/integration/shared.ts` for:
- `clearDb()` — clears all tables between tests
- `closeAllConnections()` — cleanup after tests
- Helper functions for creating test data

**Example Test Pattern**:
```typescript
describe('TenantIsolation', () => {
  beforeEach(async () => {
    await clearDb();
    // Create test orgs, projects, reports
  });

  it('should reject cross-tenant access', async () => {
    // Create report in org1
    await createReport({ organisationId: org1Id });
    // Query with org2 should return empty
    const results = await repo.getAll(undefined, [org2Id]);
    expect(results).toHaveLength(0);
  });
});
````

### Unit Tests (Mocking Allowed)

These tests CAN use mocks because they test business logic, not database behavior:

| Test Area             | Scenarios                                   | Priority    |
| --------------------- | ------------------------------------------- | ----------- |
| Data mapping          | `_mapReport()` transforms DB rows correctly | Should have |
| Validation logic      | Input validation, error handling            | Should have |
| Business rules        | Calculation logic, state transitions        | Should have |
| Service orchestration | Job flow, API calls (mock external deps)    | Should have |

**⚠️ Warning**: Do NOT mock the database for:

- Testing FK constraint behavior (SET NULL, CASCADE)
- Testing unique constraint enforcement
- Testing tenant isolation/RBAC at the query level
- Testing complex WHERE clause logic

````

**Guidelines**:
- **Default to integration tests** for repository methods
- **Use test containers** — they spin up real Postgres via Docker Compose
- **Identify FK/constraint tests early** — these are commonly missed
- **Document test data setup** — what helper functions exist in `shared.ts`
- **Reference existing patterns** — link to similar test files

**Example - Bad vs Good**:

❌ **Bad**: "Add unit tests for the new repository"

✅ **Good**:
```markdown
### Integration Tests Required

| Test | File | Reason |
|------|------|--------|
| Tenant isolation in `getAll` | `merger-form-repo.test.ts` | Security: prevent cross-org data leakage |
| FK SET NULL on file delete | `merger-form-repo.test.ts` | Extracts must survive file deletion |
| NULL question_id unique constraint | Requires real DB | COALESCE index can't be tested with mocks |
````

---

### 8. Implementation Phases

**Purpose**: Break down work into logical phases for planning.

**Format**:

```markdown
## Implementation Phases

### Phase 1: [Phase Name]

- Task 1
- Task 2
- Task 3

### Phase 2: [Phase Name]

- Task 1
- Task 2
```

**Guidelines**:

- **Don't include timelines** — those belong in project management tools
- Focus on **logical dependencies** (what must come first)
- Group related work together
- Keep tasks high-level (not implementation details)

---

### 9. Open Questions

**Purpose**: Explicitly list decisions that need to be made before/during implementation.

**Format**:

```markdown
## Open Questions Requiring Answers

1. **Question Topic**: What needs to be decided? Why does it matter?
2. **Question Topic**: What needs to be decided? Why does it matter?
```

**Guidelines**:

- **Don't duplicate TLDR** — if it's in TLDR, don't repeat here
- Explain **why** the question matters (what decision it blocks)
- Include **who needs to answer** if relevant
- Update as questions get answered (move to "Decisions Made" section)

---

### 10. Risk Mitigation

**Purpose**: Identify critical risks and how to mitigate them.

**Format**:

```markdown
## Risk Mitigation

### Critical Risks

**Risk Name**: Brief mitigation strategy.

**Risk Name**: Brief mitigation strategy.
```

**Guidelines**:

- **Only include critical risks** — not every possible issue
- Focus on risks that could **derail the project**
- Keep mitigation strategies **actionable and brief**
- Don't create a long list — 3-5 critical risks max

---

## Key Principles

### 1. Ask Questions First

Before writing, ask the prompter:

- **What problem are we solving?** (not just "what to build")
- **What constraints exist?** (time, budget, technical, compliance)
- **What similar features exist?** (patterns to reuse)
- **What are the unknowns?** (what needs research/spikes)
- **Who are the stakeholders?** (who needs to approve decisions)

### 2. Leave Unknowns as Open Questions

**Don't guess**:

- If you don't know the answer, mark it as an open question
- Explain why it matters and what decision it blocks
- Suggest how to answer it (spike, research, stakeholder input)

**Do clarify**:

- What information is needed to answer
- Who should provide the answer
- When it needs to be answered (before Phase X)

### 3. Provide Clear Recommendations

**Always recommend**:

- Don't present options without guidance
- Explain **why** you recommend an approach
- Acknowledge trade-offs explicitly
- If no clear winner, explain why and suggest a spike

**Use clear markers**:

- ✅ **Recommended** / ❌ **Not Recommended**
- **For MVP** / **For Future**
- **Open Question** (if decision needed)

### 4. Minimize Noise

**Remove**:

- Generic benefits ("this is scalable", "this is maintainable")
- Implementation code examples (unless critical for decision-making)
- Verbose explanations of obvious concepts
- Duplicate information (if in TLDR, don't repeat)
- "Next Steps" sections (belongs in project management)

**Keep**:

- Decision-making content
- Comparison tables with recommendations
- Architecture diagrams
- Critical risks and mitigations
- Open questions that block decisions

### 5. Use Tables and Diagrams Strategically

**Tables**: Use for comparing alternatives

- Always include recommendation column
- Keep pros/cons concise
- Focus on decision criteria

**Diagrams**: Use for complex flows/structures

- ASCII diagrams for workflows
- Schema diagrams if relationships are complex
- Keep them simple and readable

---

## Example: Good vs Bad

### ❌ Bad Example

```markdown
## Database Storage

We need to store data. There are many options:

**Option 1: PostgreSQL**
PostgreSQL is a powerful relational database that provides ACID compliance and strong consistency. It's widely used in production systems and has excellent tooling. Many teams use it successfully.

**Option 2: MongoDB**
MongoDB is a NoSQL database that provides flexible schema design. It's good for rapid prototyping and can scale horizontally.

**Considerations**:

- Performance
- Scalability
- Maintainability
- Cost

**Next Steps**:

- Research both options
- Create proof of concept
- Get stakeholder approval
```

**Problems**:

- No clear recommendation
- Generic benefits (not decision-making content)
- "Next Steps" doesn't belong here
- Doesn't reference existing codebase patterns

### ✅ Good Example

```markdown
## Database Storage

| Approach                        | Pros                                                     | Cons                                                  | Recommendation                                |
| ------------------------------- | -------------------------------------------------------- | ----------------------------------------------------- | --------------------------------------------- |
| Extend existing `reports` table | - Consistent with codebase<br>- Reuses existing patterns | - May need JSONB fields for flexibility               | ✅ **Recommended** — matches existing pattern |
| New dedicated table             | - Clean separation<br>- Type-safe schema                 | - More migration work<br>- Inconsistent with codebase | ❌ Not recommended — breaks existing patterns |

**Open Question**: Do we need dedicated table for input fields, or add JSONB params to `reports` table?
```

**Why it's better**:

- Clear recommendation with rationale
- References existing codebase
- Identifies open question
- Focused on decision-making

---

## Checklist

Before finalizing a technical approach document:

- [ ] **TLDR section** includes key decisions, open questions, and success metrics
- [ ] **Table of contents** matches all major sections
- [ ] **Architecture patterns** reference actual codebase patterns
- [ ] **Base class contracts** documented if extending abstract classes/interfaces
- [ ] **All inherited abstract methods** listed with implementation patterns and file references
- [ ] **Non-obvious semantics** called out (e.g., parameter meanings, table usage)
- [ ] **Comparison tables** include recommendation column
- [ ] **Diagrams** are simple and readable
- [ ] **Testing strategy** identifies integration vs unit test needs
- [ ] **Integration tests** specified for: tenant isolation, FK constraints, unique constraints
- [ ] **Test containers** mandated for database behavior tests (no mocking DB for these)
- [ ] **Open questions** explain why they matter
- [ ] **Risks** are critical only (3-5 max)
- [ ] **No duplicate content** (TLDR vs detailed sections)
- [ ] **No generic benefits** or obvious statements
- [ ] **No implementation code** unless critical for decisions
- [ ] **No "Next Steps"** section
- [ ] **All recommendations** are clearly marked

---

## Integration with Other Documents

### Relationship to `spec.md`

- **`spec.md`**: **What** to build (product requirements, user stories, acceptance criteria)
- **`implementation-solutions.md`**: **How** to build it (technical approaches, decisions, architecture)

**Key Difference**:

- Spec focuses on **user-facing deliverables**
- Implementation focuses on **technical decisions**

### Relationship to `code-standards.md`

- **`code-standards.md`**: **How to write code** (patterns, conventions, best practices)
- **`implementation-solutions.md`**: **What technical approach to take** (which patterns to use, which libraries, which architecture)

**Key Difference**:

- Code standards are **always applicable**
- Implementation solutions are **feature-specific**

---

## Usage

**When creating a new technical approach document**:

1. **Read the spec** (`docs/plans/[ticket]/spec.md`) to understand requirements
2. **Ask key questions** (see "Ask Questions First" section)
3. **Research existing patterns** in the codebase
4. **Draft the document** following this structure
5. **Review against checklist** before finalizing
6. **Update as decisions are made** (move open questions to decisions)

**When reviewing a technical approach document**:

1. Check TLDR — can you understand key decisions quickly?
2. Verify recommendations — are they clear and justified?
3. Check open questions — are unknowns identified?
4. Validate against codebase — do patterns actually exist?
5. Assess completeness — are critical decisions covered?

---

## Maintenance

- **Update frequency**: When new decisions are made or patterns change
- **Ownership**: Technical lead or architect maintains these documents
- **Versioning**: Update when major decisions change
- **Feedback**: Incorporate learnings from implementation into future documents
