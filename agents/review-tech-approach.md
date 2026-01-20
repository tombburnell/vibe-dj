# Review Technical Approach Document — Agent Guide

This guide helps review technical approach documents for completeness, correctness, and implementation readiness. Use this before approving a tech approach for implementation.

## Purpose

Tech approach reviews should:

- **Catch gaps** before implementation begins (not after bugs are found)
- **Validate patterns** actually exist in the codebase
- **Ensure inherited obligations** are fully documented
- **Verify recommendations** are clear and justified
- **Identify missing detail** that will cause implementation issues

---

## Review Process

### Phase 1: Quick Scan (2 minutes)

1. **Read TLDR** — Can you understand key decisions in 30 seconds?
2. **Check structure** — Does it follow the standard template?
3. **Count open questions** — Are unknowns explicitly listed?

If TLDR is unclear or structure is wrong, **stop and request revision**.

---

### Phase 2: Pattern Validation (5-10 minutes)

For each "Architecture Pattern to Reuse":

| Check        | Question                                                    | Action if Failed                                   |
| ------------ | ----------------------------------------------------------- | -------------------------------------------------- |
| **Exists**   | Does the referenced pattern actually exist in the codebase? | Verify file paths, grep for classes/functions      |
| **Correct**  | Is the pattern description accurate?                        | Read the actual code, compare to description       |
| **Complete** | Are ALL aspects of the pattern documented?                  | Check for inherited methods, required tables, etc. |

**Common Gaps to Look For**:

- "Extend X pattern" without listing what X requires
- File paths that don't exist or are outdated
- Descriptions that don't match actual implementation

---

### Phase 3: Base Class & Interface Contract Review (CRITICAL)

**This is where most implementation bugs originate.**

For each abstract class or interface being extended:

#### 3a. Identify All Inherited Obligations

```bash
# Find abstract methods in the base class
grep -n "abstract" bff/src/repositories/abstract-report-repo.ts
```

#### 3b. Verify Documentation Completeness

| Abstract Method        | Documented? | Implementation Pattern Shown? | Reference File? | Non-obvious Semantics? |
| ---------------------- | ----------- | ----------------------------- | --------------- | ---------------------- |
| `getById`              | ✅/❌       | ✅/❌                         | ✅/❌           | ✅/❌                  |
| `updateStatus`         | ✅/❌       | ✅/❌                         | ✅/❌           | ✅/❌                  |
| `upsertAttachment`     | ✅/❌       | ✅/❌                         | ✅/❌           | ✅/❌                  |
| `getAttachmentContent` | ✅/❌       | ✅/❌                         | ✅/❌           | ✅/❌                  |
| `upsertAnalysis`       | ✅/❌       | ✅/❌                         | ✅/❌           | ✅/❌                  |

#### 3c. Red Flags

- ❌ "Follow existing pattern" without specifying WHICH methods
- ❌ Missing table showing all abstract methods
- ❌ No reference files for implementation examples
- ❌ Parameters with non-obvious meanings not explained
- ❌ Different tables/approaches used across existing repos (which one to follow?)

#### 3d. Required Output

If extending a base class, tech approach MUST include:

```markdown
## Base Class Contracts

### Extending `[ClassName]`

| Method    | Purpose | Implementation Pattern | Reference         |
| --------- | ------- | ---------------------- | ----------------- |
| `method1` | ...     | ...                    | `file.ts:L##-L##` |
| `method2` | ...     | ...                    | `file.ts:L##-L##` |

**⚠️ Common Mistakes**: [List any non-obvious semantics]
```

---

### Phase 4: Gap Analysis

Compare the tech approach against:

#### 4a. Spec Requirements

| Spec Requirement | Tech Approach Coverage      | Gap?  |
| ---------------- | --------------------------- | ----- |
| UC1, AC1-3       | Which section addresses it? | ✅/❌ |
| UC2, AC4-5       | Which section addresses it? | ✅/❌ |
| ...              | ...                         | ...   |

#### 4b. Existing Code Patterns

For each similar feature in the codebase:

| Existing Feature | Pattern Used                                 | Tech Approach Matches? | Gap?         |
| ---------------- | -------------------------------------------- | ---------------------- | ------------ |
| Document Review  | AbstractReportRepo + attachmentContent table | ✅/❌                  | Describe gap |
| RFI              | AbstractReportRepo + attachmentContent table | ✅/❌                  | Describe gap |
| CSI              | AbstractReportRepo + attachmentContent table | ✅/❌                  | Describe gap |

#### 4c. Implementation Detail Gaps

| Area                | Sufficient Detail? | What's Missing? |
| ------------------- | ------------------ | --------------- |
| Database schema     | ✅/❌              | ...             |
| Repository methods  | ✅/❌              | ...             |
| Service layer       | ✅/❌              | ...             |
| Queue/job structure | ✅/❌              | ...             |
| API endpoints       | ✅/❌              | ...             |
| UI components       | ✅/❌              | ...             |

---

### Phase 5: Decision Validation

For each recommendation:

| Decision   | Recommendation Clear? | Rationale Provided? | Trade-offs Acknowledged? |
| ---------- | --------------------- | ------------------- | ------------------------ |
| Decision 1 | ✅/❌                 | ✅/❌               | ✅/❌                    |
| Decision 2 | ✅/❌                 | ✅/❌               | ✅/❌                    |

---

## Review Checklist

### Structure & Completeness

- [ ] TLDR includes key decisions, open questions, success metrics
- [ ] Table of contents matches all sections
- [ ] All comparison tables have recommendation column

### Pattern Documentation

- [ ] All referenced patterns exist in codebase (verified via grep/read)
- [ ] File paths are correct and current
- [ ] Pattern descriptions match actual implementations

### Base Class Contracts (CRITICAL)

- [ ] All abstract classes/interfaces being extended are identified
- [ ] ALL abstract methods are listed in a table
- [ ] Each method has implementation pattern described
- [ ] Each method has reference file with line numbers
- [ ] Non-obvious parameter semantics are called out
- [ ] Common mistakes are documented

### Gap Analysis

- [ ] All spec requirements are addressed
- [ ] Approach matches existing codebase patterns
- [ ] No unexplained deviations from established patterns

### Implementation Readiness

- [ ] Sufficient detail for implementer to proceed without guessing
- [ ] No ambiguous phrases like "follow existing pattern" without specifics
- [ ] Open questions are genuine unknowns, not missing research

---

## Review Output Template

```markdown
## Tech Approach Review: [Document Name]

**Reviewer**: [Name]
**Date**: [Date]
**Verdict**: ✅ Approved / ⚠️ Revisions Needed / ❌ Major Gaps

### Summary

[1-2 sentence summary of review findings]

### Gaps Found

#### Critical (Blocks Implementation)

1. [Gap description + what's needed to fix]
2. ...

#### Important (Should Fix Before Implementation)

1. [Gap description + what's needed to fix]
2. ...

#### Minor (Can Fix During Implementation)

1. [Gap description]
2. ...

### Base Class Contract Review

| Class                | Methods Documented | Gaps                                            |
| -------------------- | ------------------ | ----------------------------------------------- |
| `AbstractReportRepo` | 3/5                | Missing: upsertAttachment, getAttachmentContent |

### Pattern Validation

| Pattern             | Verified | Issues                                     |
| ------------------- | -------- | ------------------------------------------ |
| Report Type Pattern | ✅       | None                                       |
| Document Processing | ⚠️       | Missing attachment_content table reference |

### Recommendations

1. [Specific action to address gaps]
2. [Specific action to address gaps]
```

---

## Common Review Findings

### 1. "Extend X Pattern" Without Details

**Problem**: Doc says "follow AbstractReportRepo pattern" but doesn't list methods.

**Fix Required**: Add table showing all abstract methods with implementation patterns.

### 2. Wrong Table/Approach Assumed

**Problem**: Implementer assumes `report_files` for attachments, but should use `attachment_content`.

**Fix Required**: Explicitly document which table for what purpose, with reference to existing repo.

### 3. Missing Non-Obvious Semantics

**Problem**: Parameter `attachment: string[]` appears to be file IDs but is actually document text.

**Fix Required**: Add "Common Mistakes" section explaining non-obvious semantics.

### 4. Pattern Drift

**Problem**: Different repos implement the same abstract method differently.

**Fix Required**: Identify the CORRECT pattern and document why (or note as tech debt to consolidate).

---

## Integration with Other Reviews

- **Before Plan Review**: Tech approach should be reviewed first
- **After Spec Review**: Tech approach should reference approved spec
- **Feeds Into**: Implementation plan review (see `agents/review-plan.md`)

---

## Maintenance

- **Update when**: New abstract classes added, patterns change, common issues discovered
- **Ownership**: Senior engineers / tech leads
- **Feedback loop**: Add new "Common Review Findings" when issues are discovered post-implementation
