---
title: '[Feature/Task Name] - Work Log'
plan_reference: '/plan/[plan-name].md'
branch: '[branch-name]'
date_started: 'YYYY-MM-DD'
last_updated: 'YYYY-MM-DD'
status: 'Not Started' | 'In Progress' | 'Blocked' | 'In Review' | 'Completed'
owner: '[Developer Name/Handle]'
reviewers: ['[Reviewer 1]', '[Reviewer 2]']
tags: ['feature', 'refactor', 'bugfix', 'upgrade', 'infrastructure']
---

# Work Log: [Feature/Task Name]

![Status](https://img.shields.io/badge/status-in_progress-yellow)
![Progress](https://img.shields.io/badge/progress-0%25-blue)

## Overview

**Objective**: [Brief description of what this work accomplishes]

**Related Plan**: [Link to implementation plan](../plan/[plan-name].md)

**Branch**: `[branch-name]`

---

## 1. Progress Summary

### Overall Progress

| Phase | Status | Progress | Started | Completed |
|-------|--------|----------|---------|-----------|
| Phase 1: [Name] | 🔴 Not Started | 0% | - | - |
| Phase 2: [Name] | 🟡 In Progress | 50% | YYYY-MM-DD | - |
| Phase 3: [Name] | 🟢 Completed | 100% | YYYY-MM-DD | YYYY-MM-DD |

**Legend**: 🔴 Not Started | 🟡 In Progress | 🔵 Blocked | 🟣 In Review | 🟢 Completed

### Quick Stats

| Metric | Count |
|--------|-------|
| Total Tasks | 0 |
| Completed | 0 |
| In Progress | 0 |
| Blocked | 0 |
| Remaining | 0 |

---

## 2. Task Tracking

### Phase 1: [Phase Name]

**Goal**: [GOAL-001 from implementation plan]

| Task ID | Description | Status | Assignee | Est. Hours | Actual Hours | Notes |
|---------|-------------|--------|----------|------------|--------------|-------|
| TASK-001 | [Task description] | 🟢 Done | @dev | 2h | 1.5h | - |
| TASK-002 | [Task description] | 🟡 WIP | @dev | 4h | - | See blocker below |
| TASK-003 | [Task description] | 🔴 TODO | - | 3h | - | - |

### Phase 2: [Phase Name]

**Goal**: [GOAL-002 from implementation plan]

| Task ID | Description | Status | Assignee | Est. Hours | Actual Hours | Notes |
|---------|-------------|--------|----------|------------|--------------|-------|
| TASK-004 | [Task description] | 🔴 TODO | - | - | - | - |
| TASK-005 | [Task description] | 🔴 TODO | - | - | - | - |

---

## 3. Files Modified

### Changed Files

| File Path | Change Type | Status | Related Task | PR/Commit |
|-----------|-------------|--------|--------------|-----------|
| `src/module/file.ts` | Modified | ✅ Done | TASK-001 | #123 |
| `src/components/new.tsx` | Created | 🔄 WIP | TASK-002 | - |
| `tests/file.test.ts` | Created | 📝 Planned | TASK-003 | - |

**Change Types**: Created | Modified | Deleted | Renamed | Moved

### New Dependencies Added

| Package | Version | Purpose | Task |
|---------|---------|---------|------|
| `package-name` | ^1.0.0 | Description | TASK-001 |

### Configuration Changes

| File | Change Description | Task |
|------|-------------------|------|
| `config/app.ts` | Added new env variable | TASK-002 |

---

## 4. Implementation Details

### Key Decisions Made

| ID | Decision | Rationale | Date | Alternatives Considered |
|----|----------|-----------|------|------------------------|
| DEC-001 | [Decision description] | [Why this approach] | YYYY-MM-DD | [Other options] |

### Code Patterns Used

```markdown
### Pattern: [Pattern Name]
- **Location**: `path/to/implementation`
- **Purpose**: [Why this pattern was used]
- **Reference**: [Link to similar pattern in codebase or docs]
```

### Architecture Notes

[Diagram or description of any architectural changes]

```
┌─────────────┐     ┌─────────────┐
│  Component  │────▶│   Service   │
└─────────────┘     └─────────────┘
```

---

## 5. Testing

### Test Coverage

| Test Type | File | Status | Related Task |
|-----------|------|--------|--------------|
| Unit | `tests/unit/module.test.ts` | ✅ Passing | TASK-001 |
| Integration | `tests/integration/flow.test.ts` | 🔄 WIP | TASK-003 |
| E2E | `tests/e2e/feature.test.ts` | 📝 Planned | TASK-005 |

### Manual Testing Checklist

- [ ] Happy path works as expected
- [ ] Edge cases handled
- [ ] Error states display correctly
- [ ] Performance acceptable
- [ ] Accessibility verified
- [ ] Cross-browser tested (if applicable)
- [ ] Mobile responsive (if applicable)

### Test Commands

```bash
# Run all tests for this feature
npm test -- --grep "feature-name"

# Run specific test file
npm test path/to/test.ts

# Run with coverage
npm test -- --coverage
```

---

## 6. Blockers & Issues

### Active Blockers

| ID | Description | Severity | Blocking Tasks | Owner | Created | Resolution |
|----|-------------|----------|----------------|-------|---------|------------|
| BLK-001 | [Blocker description] | 🔴 High | TASK-002, TASK-003 | @dev | YYYY-MM-DD | [Status/ETA] |

**Severity**: 🔴 High (blocks release) | 🟡 Medium (blocks tasks) | 🟢 Low (workaround exists)

### Resolved Blockers

| ID | Description | Resolution | Resolved Date |
|----|-------------|------------|---------------|
| BLK-000 | [Resolved blocker] | [How it was resolved] | YYYY-MM-DD |

### Open Questions

- [ ] Q1: [Question needing clarification] → Assigned to: @person
- [x] Q2: [Answered question] → Answer: [Resolution]

---

## 7. Time Tracking

### Daily Log

| Date | Hours | Tasks Worked | Notes |
|------|-------|--------------|-------|
| YYYY-MM-DD | 4h | TASK-001, TASK-002 | Completed initial setup |
| YYYY-MM-DD | 6h | TASK-002 | Debugging edge case |

### Time Summary

| Category | Estimated | Actual | Variance |
|----------|-----------|--------|----------|
| Development | 20h | 15h | -5h |
| Testing | 8h | 10h | +2h |
| Code Review | 4h | 2h | -2h |
| Documentation | 2h | 2h | 0h |
| **Total** | **34h** | **29h** | **-5h** |

---

## 8. Code Review

### Review Status

| PR | Title | Status | Reviewer | Comments | Link |
|----|-------|--------|----------|----------|------|
| #123 | feat: add feature X | 🟢 Merged | @reviewer | 5 resolved | [Link](#) |
| #124 | test: add tests for X | 🟡 In Review | @reviewer | 2 pending | [Link](#) |

### Review Feedback Summary

| Feedback | Action Taken | Status |
|----------|--------------|--------|
| [Reviewer comment/suggestion] | [How it was addressed] | ✅ Resolved |

---

## 9. Deployment & Release

### Environment Status

| Environment | Version/Commit | Deployed | Status |
|-------------|----------------|----------|--------|
| Development | `abc123` | YYYY-MM-DD | ✅ Healthy |
| Staging | `abc123` | YYYY-MM-DD | ✅ Healthy |
| Production | - | - | 📝 Pending |

### Deployment Checklist

- [ ] Feature flag configured (if applicable)
- [ ] Database migrations run
- [ ] Environment variables set
- [ ] Monitoring/alerts configured
- [ ] Rollback plan documented
- [ ] Stakeholders notified

### Release Notes Draft

```markdown
## [Version] - YYYY-MM-DD

### Added
- [New feature description]

### Changed
- [Changes to existing functionality]

### Fixed
- [Bug fixes]
```

---

## 10. Session Notes

### Session: YYYY-MM-DD

**Focus**: [What was worked on]

**Accomplishments**:
- [x] Completed X
- [x] Fixed Y

**Challenges**:
- [Challenge faced and how it was handled]

**Next Steps**:
- [ ] Continue with Z
- [ ] Review PR

**Context for Next Session**:
```
[Important state/context that should be remembered]
- Currently working on: [file/feature]
- Left off at: [specific point]
- Need to investigate: [pending items]
```

---

## 11. References

### Related Links

- **Implementation Plan**: [/plan/plan-name.md](../plan/plan-name.md)
- **Design Doc**: [Link if applicable]
- **Ticket/Issue**: [JIRA/GitHub Issue link]
- **Figma/Designs**: [Link if applicable]

### Relevant Documentation

- [Internal doc 1](#)
- [External reference](#)

### Related PRs/Commits

| Type | Reference | Description |
|------|-----------|-------------|
| PR | #123 | Main feature implementation |
| Commit | `abc1234` | Critical fix |

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| YYYY-MM-DD | @dev | Initial worklog created |
| YYYY-MM-DD | @dev | Updated Phase 1 progress |
