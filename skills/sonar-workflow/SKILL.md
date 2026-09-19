---
name: sonar-workflow
description: Fix SonarQube code quality issues for a pull request. Auto-fixes trivial issues (formatting, unused imports) and requests approval for complex issues (security, bugs). Integrates with commit-workflow and pr-workflow skills.
allowed-tools: Bash
---

# SonarQube Quality Workflow

This skill helps fix SonarQube code quality issues for a pull request by prioritizing issues, auto-fixing trivial problems, and requesting approval for complex changes.

## When to Use

- After creating a PR when SonarQube analysis is available
- When asked to "fix SonarQube issues" or "improve code quality"
- When quality gate is failing on a PR

## Prerequisites

- PR must exist for current branch
- SonarQube project configured in `sonar-project.properties`
- SonarQube analysis completed for the PR

## Issue Classification

### Trivial (Auto-fix without approval)

- Severity: `INFO` or `LOW`
- Type: Code smell only
- Single-file changes
- Impact: `MAINTAINABILITY` only
- Keywords: "unused", "console.log", "formatting", "whitespace", "empty", "import order"

### Complex (User approval required)

- All security hotspots
- Severity: `HIGH`, `BLOCKER`, `CRITICAL`
- Type: Bug, Vulnerability
- Coverage gaps (requires test writing)
- Code duplications (requires refactoring)
- Medium severity affecting multiple files

## Workflow

### 1. Verify PR Exists

Check if PR exists for current branch:

```bash
gh pr list --head "$(git branch --show-current)" --state open
```

Exit if no PR found with message: "No PR found for current branch. Create PR first using pr-workflow skill."

Extract PR number from output.

### 2. Get PR Details

```bash
gh pr view <pr-number> --json number,headRefName,baseRefName
```

Extract: PR number, branch name, base branch.

### 3. Get SonarQube Project Key

```bash
grep "^sonar.projectKey=" sonar-project.properties | cut -d'=' -f2
```

Use the extracted project key for all SonarQube operations.

Verify project exists using `search_my_sonarqube_projects`.

### 4. Fetch Issues by Priority

Process in strict priority order:

#### a. Security Hotspots (Highest Priority)

```bash
# Tool: search_security_hotspots(projectKey, pullRequest, status=["TO_REVIEW"])
# For each: show_security_hotspot(hotspotKey)
```

Classification: Always complex (require approval).

#### b. BLOCKER/HIGH Issues

```bash
# Tool: search_sonar_issues_in_projects(projects=[projectKey], pullRequestId, severities=["BLOCKER","HIGH"])
# For each: show_rule(ruleKey) for remediation guidance
```

Classification: Always complex (require approval).

#### c. Coverage Issues

```bash
# Tool: search_files_by_coverage(projectKey, pullRequest, maxCoverage=70)
# For each: get_file_coverage_details(fileKey, pullRequest)
```

Classification: Always complex (requires test writing).

#### d. Code Duplications

```bash
# Tool: search_duplicated_files(projectKey, pullRequest)
# For each with >5% duplication: get_duplications(fileKey, pullRequest)
```

Classification: Always complex (requires refactoring).

#### e. MEDIUM/LOW/INFO Issues

```bash
# Tool: search_sonar_issues_in_projects(projects=[projectKey], pullRequestId, severities=["MEDIUM","LOW","INFO"])
# For each: show_rule(ruleKey)
```

Classification: Apply trivial vs complex logic based on rule keywords and type.

### 5. Categorize Issues

For each issue:

- Check severity + type + rule keywords
- Assign to `trivial_issues[]` or `complex_issues[]`
- Store: key, file, line, rule, description, fix_guidance

### 6. Auto-Fix Trivial Issues

For each trivial issue:

1. Read file with issue
2. Apply automated fix based on rule type:
   - Unused imports: Remove import statement
   - `console.log`: Remove or comment out
   - Formatting: Apply suggested formatting
   - Empty blocks: Add TODO comment or remove
3. Verify fix: `analyze_code_snippet(projectKey, fileContent, language, scope)`
4. If new issues introduced, rollback and move to complex queue
5. If successful, add to `fixed_issues[]`

### 7. Fix Complex Issues with Approval

For each complex issue (in priority order):

1. Present to user:
   - Issue type, severity, file:line
   - Rule description and remediation guidance
   - Code context (show relevant lines)
2. Ask: "Fix this issue? [yes/no/skip remaining]"
3. If yes:
   - Read file
   - Apply fix based on rule guidance
   - Verify with `analyze_code_snippet`
   - If successful, add to `fixed_issues[]`
   - If failed, report and continue
4. If "skip remaining", break loop

### 8. Commit Changes

Group fixes by type for logical commits using `commit-workflow` skill:

```bash
# Security fixes
Skill(skill="commit-workflow")
# Use format: fix(security): <description>

# Bug fixes
Skill(skill="commit-workflow")
# Use format: fix(<scope>): <description>

# Code smell fixes
Skill(skill="commit-workflow")
# Use format: refactor(<scope>): <description>
```

**Commit Message Format:**

```
<type>(<scope>): <description>

WHY: SonarQube rule <rule-key> - <rule reason>
```

Example:

```
fix(auth): remove unused import in login handler

WHY: SonarQube rule javascript:S1128 - unused imports increase bundle size
```

### 9. Mark Issues Resolved

For each fixed issue:

```bash
# Trivial code smells
change_sonar_issue_status(key, status=["accept"])

# Security hotspots
change_security_hotspot_status(hotspotKey, status=["REVIEWED"], resolution=["FIXED"])

# Complex bugs/vulnerabilities
change_sonar_issue_status(key, status=["accept"])
```

### 10. Update PR Description

Add new section to PR template after "## Test Results":

```markdown
## SonarQube Fixes

Fixed X issues across Y files:

- Security: Z hotspots reviewed and fixed
- Bugs: A issues fixed
- Code Smells: B issues fixed
- Coverage: C files improved
- Duplications: D blocks refactored
```

Invoke `pr-workflow` skill to update PR with enhanced description.

## Safety Rules

- **NEVER auto-fix security hotspots** - always require approval
- **NEVER auto-fix HIGH/BLOCKER severity** - always require approval
- **VERIFY after each fix** - use `analyze_code_snippet` to ensure no new issues
- **ROLLBACK failed fixes** - revert file if verification fails
- **ONE-BY-ONE for complex** - never batch complex fixes
- **PRESERVE functionality** - only fix code quality, don't change behavior
- **RESPECT exclusions** - honor `sonar.exclusions` (node_modules, .next, dist, etc.)
- **NEVER commit secrets** - reject any rule fix that exposes credentials

## Examples

### Example 1: Auto-fixing Unused Imports (Trivial)

Issue: `javascript:S1128` - Unused import in `apps/web/lib/auth.ts:5`

Action:

1. Read file
2. Remove unused import line
3. Verify with `analyze_code_snippet`
4. Commit: `refactor(auth): remove unused imports`
5. Mark resolved: `change_sonar_issue_status(key, status=["accept"])`

### Example 2: Fixing Security Hotspot (Complex)

Issue: Security hotspot - "Make sure this CORS policy is safe here" in `apps/web/api/route.ts:12`

Action:

1. Present to user with rule details
2. Wait for approval
3. If approved:
   - Read file and context
   - Restrict CORS origins to whitelist
   - Verify fix
   - Commit: `fix(api): restrict CORS to whitelisted origins`
4. Mark resolved: `change_security_hotspot_status(hotspotKey, status=["REVIEWED"], resolution=["FIXED"])`

### Example 3: Coverage Gap (Complex)

Issue: File `apps/web/lib/utils.ts` has 45% coverage

Action:

1. Present coverage details to user
2. Show uncovered lines
3. Wait for approval
4. If approved:
   - Write unit tests for uncovered code paths
   - Verify coverage improvement
   - Commit: `test(utils): add unit tests for utility functions`
5. Note: Coverage improvements don't require marking issues resolved (metric-based)

## Edge Cases

- **No PR found**: Exit with helpful message
- **SonarQube project not found**: Exit with error
- **No issues found**: Success message: "No SonarQube issues found for this PR. Quality gate passed!"
- **Fix verification fails**: Rollback file, log error, continue to next issue
- **All fixes rejected**: Exit gracefully: "No fixes applied. Issues remain in SonarQube."
- **Multiple SonarQube projects**: Use project key from `sonar-project.properties`
