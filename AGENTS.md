# Copilot Beta - Legal AI Platform

<!-- Cursor reads both ./rules/cursor and AGENTS.md -->

## Project Overview

- **CONFIDENTIAL** legal AI platform for CompetitionAI
- Monorepo structure: `copilot/` (frontend), `bff/` (backend), `infra-aws-dev/` (infrastructure)
- Strict TypeScript usage across all subprojects
- Shared types between frontend/backend via `@shared/types`

## For AI Tools - Quick Start

When working on this codebase as an AI assistant:

1. **Read this file (`AGENTS.md`)** - Project structure, build/test commands, coding style, testing guidelines
2. **Reference `code-standards.md`** - Detailed coding standards (architecture, types, security, performance) when writing code
3. **Use `agents/code-review.md`** - Structured code review prompt when reviewing PRs/branches
4. **Check `docs/`** - Architecture documentation (`docs/architecture.md`, `docs/architectural-patterns.md`, `docs/background-jobs.md`, `docs/db-schema.md`)

**Key Files:**

- `AGENTS.md` (this file) - Project guidelines and commands
- `code-standards.md` - Coding standards and best practices
- `agents/code-review.md` - Code review agent prompt
- `agents/pr-checklist.md` - PR quality checklist (common issues from historical reviews)
- `docs/` - Technical architecture documentation

**Subproject-Specific Rules:**

- Subproject-specific rules may exist in `copilot/.cursor/rules`, `bff/.cursor/rules`, `infra-aws-dev/.cursor/rules` (optional extensions)
- When working in a specific subproject, refer to its dedicated rules file for detailed guidance

---

# CRITICAL RULES

- NEVER Delete files without asking for permission first
- Warn before ever deleting a file that is not committed to git even with permission.
- Use existing test patterns
- Keep api routes thin and business logic in services
- **Throw errors on failures, don't return null** - Services and job processors should throw on errors, not return null (return null only for "not found" scenarios)
- **Always log errors in catch blocks** - Never have empty catch blocks; log with context before re-throwing
- **When adding env vars**: Update `.kamal/secrets-common` AND `.env.example` for local dev
- **When fixing test failures: If it's ambiguous whether to change code or tests, ASK the user first. Generally prefer to fix code to meet tests rather than changing tests.**
- **When user pastes test error logs: If ambiguous whether the test or code should change, ASK for clarification before making any changes.**

## Project Structure & Module Organization

- `copilot/`: Next.js 15 frontend; folders include `src/app`, `src/components`, `src/hooks`, shared utilities in `src/lib`, and tests in `src/**/__tests__`.
- `bff/`: Express + BullMQ backend; request flows live in `src/routers`, jobs in `src/orchestration`, shared types/utilities in `shared/`, and Drizzle schema + migrations in `drizzle/`.
- `infra-aws-dev/`: CDK stacks for AWS resources. Supporting ops assets: `config/` deploy manifests, `grafana/` dashboards, `alloy.river` agent wiring.

### Layer Responsibilities (Strict)

- **Routers**: HTTP concerns only - request parsing, response formatting, delegate to services
- **Services**: All business logic and orchestration
- **Repositories**: Database operations ONLY - no business logic, no queue/Redis operations
- **Orchestration** (`src/orchestration/`): BullMQ flows, jobs, queue operations - NOT in repositories
- **Split large files**: If a file exceeds ~500 lines, split into smaller focused modules

## Build, Test, and Development Commands

- Start Docker once with `npm run colima:start`, then boot the full stack via `npm run dev` (runs `docker-compose.local.yml`).
- Frontend (`copilot`): `npm run dev` (Next.js dev), `npm run build`, `npm run lint`, `npm run test`, `npm run story`.
- Backend (`bff`): `npm run dev` (tsx watch), `npm run build` (esbuild), `npm run test`, `npm run migrate`, `npm run serve` (dist server). Type-check both apps with the root `npm run tsc`.

## Coding Style & Naming Conventions

- Use Node 22.x (`.nvmrc`) and npm. Prettier + lint-staged enforce formatting; run `npm run format` locally before large refactors.
- Follow ESLint defaults: React components PascalCase, hooks prefixed with `use`, Next.js route folders lowercase. Backend modules prefer camelCase and queue handlers mirror job names.
- Tailwind drives styling; keep utility groupings consistent and reuse shared components.

### Detailed Naming Conventions

- **React components**: PascalCase (e.g., `UserProfile.tsx`)
- **Functions, variables, file names**: camelCase (e.g., `getUserData.ts`)
- **CSS classes and file paths**: kebab-case (e.g., `user-profile.css`)
- **API routes**: Prefix with `/api/` and follow REST conventions
- **TypeScript interfaces/types**: PascalCase (e.g., `UserProfile`, `ApiResponse`)

## TypeScript Standards (Project-Wide)

- Use strict TypeScript configuration across all subprojects
- Prefer explicit typing over `any` (except where explicitly allowed)
- Use shared types from `@shared/types` for cross-project consistency
- Run `npm run tsc` before any commits to ensure type safety
- Use proper interface definitions
- Follow existing import/export patterns
- **ALWAYS reference `docs/code-standards.md`** when writing code for detailed type safety guidelines

## Testing Guidelines

- Frontend tests rely on Vitest + Testing Library (`copilot/vitest.config.js`); suites live near code in `__tests__` directories and share setup from `src/test/setupTests.ts`.
- Backend tests run under Vitest in Node (`bff/vitest.config.ts`) with Supertest helpers in `src/__tests__`; add fixtures alongside suites and mock BullMQ when integration is unnecessary.
- For every feature, cover happy-path plus RBAC/edge cases, ensure `npm run tsc` passes, and execute both test suites before pushing.
- **Test failures: When a test fails and it's unclear whether the issue is in the code or the test, ASK the user before making changes. Default to fixing the code to match the test expectations rather than modifying tests. Tests represent the intended behavior, so code should conform to tests unless the test itself is incorrect.**
- **After fixing test failures: Always re-run the failing tests to confirm the fix actually works. Don't assume the fix is correct without verification.**
- **Handling test error logs: When a user pastes test error logs or failure output:**
  - **Analyze the error** - Understand what the test is expecting vs. what the code is doing
  - **Check for ambiguity** - If it's unclear whether the test expectation is wrong or the code implementation is wrong, **ASK the user for clarification before making changes**
  - **Default behavior** - When ambiguous, prefer fixing the code to match test expectations (tests represent intended behavior), but **always confirm with the user first**
  - **Provide context** - When asking, explain what you see in the error, what the test expects, what the code does, and why it's ambiguous
  - **Don't assume** - Never change tests or code without user confirmation when the root cause is ambiguous

## Commit & Pull Request Guidelines

- **⚠️ IMPORTANT: Before committing, check if you're on the main branch. If so, suggest to user to create a feature branch first. Never commit directly to main/master branches without approval.**
- Commit subjects stay imperative and usually lead with the tracking ID (e.g., `#603 feat: align report banner`); keep unrelated changes separate.
- Husky's `pre-commit` runs lint-staged plus type-checks for both apps—install dependencies so the hook is active and re-run failed commands manually.
- PRs should summarise intent, link tickets, attach screenshots or sample payloads for UI/API changes, confirm docker-compose startup, and request review from the squad.

## Monorepo Patterns

- Use shared types from `bff/shared/types.ts` for cross-project consistency
- Follow existing directory structure patterns
- Maintain consistency across subprojects
- Use npm scripts for cross-project operations
- Run `npm run tsc` before commits to ensure type safety across all projects

## File Organization

- Keep feature-based organization (e.g., `/fdi/`, `/document-review/`)
- Use clear separation between UI components and business logic
- Maintain consistent naming conventions across projects
- Follow existing import/export patterns
- Organize by feature/domain rather than by file type when possible

## Development Workflow

- Ensure TypeScript checks pass (`npm run tsc`) before submitting changes
- Follow existing code style and patterns
- Test changes in development environment
- Update documentation as needed
- Create Pull Requests for all changes
- Get approval from at least one other developer
- **NO direct commits to main branches** - always use Pull Requests

## Environment & Security Tips

- Store secrets in per-service `.env` files (never commit). `npm run queues:obliterate` requires a fresh `CF_COOKIE` Cloudflare Access token.
- Infrastructure edits must flow through CDK (`infra-aws-dev` + `npx cdk diff/deploy`); console changes will be replaced on the next deployment.

### Adding New Environment Variables

When introducing new env vars, update ALL of these:

1. `.kamal/secrets-common` - for production/staging deployment
2. `config/deploy.*.yml` - environment-specific overrides if needed
3. `.env.example` or document in README - for local development
4. `bff/src/utils/env.ts` - add zod validation with sensible defaults

## Security & Confidentiality

- **NEVER commit sensitive data or API keys**
- Use environment variables for configuration
- **NO public repositories or forks** - maintain strict confidentiality
- Maintain strict access controls
- All infrastructure changes must go through CDK code
- **NO public disclosure of code or documentation** - this is proprietary software
- Maintain strict confidentiality - this is proprietary software

## Development Approach

- Follow user's requirements carefully & to the letter
- **Do not add fallbacks or additional features unless explicitly requested**
- **Do not make assumptions** - if something is unclear, ask the user rather than guessing
- **Do not scope creep** - implement only what was asked for, nothing more
- **If you think something could be useful** (validation, fallbacks, etc.), **ask the user first** before adding it
- **When handling test error logs: If it's ambiguous whether the test expectation or code implementation is wrong, ask the user for clarification before making changes. Explain what you see and why it's ambiguous.**
- **When encountering similar patterns or code duplication**: If you notice opportunities to refactor or consolidate code that's out of scope for the current task, **ASK the user first** before making changes. Suggest creating a tech debt ticket as an alternative to keep the current change focused.
- **YAGNI (You Ain't Gonna Need It)**: Don't add abstractions, wrappers, or "future-proof" code unless there's a clear, immediate need. Prefer direct, explicit implementations over generic abstractions until patterns emerge naturally.
  - **Note**: YAGNI applies to **new abstractions**, not established architectural patterns. Router → Service → Repository separation is correct architecture.
- **Keep surface area tight**: Minimize the number of methods, classes, and layers involved in a change. Avoid creating thin wrapper methods that add no value—call services directly rather than routing through unnecessary repository methods.
  - **Note**: This doesn't mean avoiding proper layer separation. Avoid **extra** delegation layers (e.g., repo method that just calls service method with identical signature).
- First think step-by-step - describe your plan for what to build in pseudocode, written out in great detail
- Confirm, then write the code!
- Always write correct, up to date, bug free, fully functional and working, secure, performant and efficient code
- Focus on readability over performance
- Fully implement all requested functionality
- Leave NO Todo's, placeholders and missing pieces
- Be sure to reference filenames
- Be concise. Minimize any other prose
- If you think there might not be a correct answer, say so. If you don't know the answer, say so instead of guessing

## Documentation Standards

When creating or editing documentation (specs, tech approaches, architecture docs, etc.):

- **Keep it concise**: Remove noise, eliminate redundancy, use direct language
- **Fast to read**: Use bullets and tables for structure, avoid long paragraphs
- **Preserve detail**: Don't summarize or lose key information—be concise but complete
- **Number everything**: Use numbered lists (1, 2, 3) and numbered items (UC1, AC1, etc.) for easy addressing and cross-referencing
- **Use tables**: Compare alternatives, show pros/cons, structure complex information
- **Use bullets**: Break down information into scannable lists
- **Examples**:
  - ✅ "UC1: User uploads documents → System processes → SoR created"
  - ✅ "AC1 (P0): System extracts 30-40 information types from documents"
  - ✅ Comparison tables with recommendation columns
  - ❌ Long paragraphs explaining concepts that could be bullets
  - ❌ Unnumbered lists that can't be referenced

## Rules Maintenance

- These rules should be updated when significant architectural changes are made
- When adding new technologies, patterns, or conventions, update the relevant rules files
- If you notice AI making suggestions that don't align with current patterns, consider updating the rules
- Keep rules in sync with actual codebase patterns and team preferences
- Review and update rules periodically to ensure they reflect current best practices
- When updating patterns, also update `docs/code-standards.md` to maintain consistency
