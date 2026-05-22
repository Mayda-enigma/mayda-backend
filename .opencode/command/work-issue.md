---
description: Fetch a GitHub issue, branch from main, work tasks with per-task commits, run quality gates, open a PR, and move it through the Mayda Project board
agent: build
---

You are executing the **Mayda work-issue routine**. Your job is to fully resolve a GitHub issue on the Mayda Project board by following a strict, step-by-step workflow. Be autonomous, methodical, and commit progress after every completed task.

---

## Input

GitHub issue number(s): **$ARGUMENTS**

If no number was provided, stop immediately and ask:
> "Please provide a GitHub issue number. Usage: `/work-issue 41` (or multiple: `/work-issue 41 42 43`)."

If multiple numbers are provided, process them **one at a time, end-to-end**. Do not interleave.

---

## Project board constants (Mayda Project, org `Mayda-enigma`)

- Project number: `1`
- Project ID: `PVT_kwDOERkXVs4BYgAL`
- Status field ID: `PVTSSF_lADOERkXVs4BYgALzhTlc34`
- Status options:
  - **In progress** = `47fc9ee4`
  - **In review**  = `df73e18b`

---

## Step 1 — Fetch the issue from GitHub

```bash
gh issue view <num> --json number,title,body,labels,assignees,url,state
```

Extract and display:
- **Label prefix** in the title (e.g. `MG-011`, `WC-007`, `BE-004`, `AI-001`). Treat this as the ticket code (`<LABEL>`) throughout.
- **Goal / context** — any opening paragraph before the task list.
- **Tasks** — every `- [ ]` checkbox, in order. Build an ordered flat list.
- **Acceptance criteria** — collect separately. Not tasks to commit; used as the definition of done.
- **References** — linked patterns, files, PoCs. Read them before writing — don't guess.

Display the parsed list before starting:

```
📋 Issue <LABEL> — <title>
Tasks (N total):
  [1] <task>
  [2] <task>
  ...
Acceptance criteria (M total):
  - <criterion>
  ...
```

---

## Step 2 — Prepare the branch

1. Ensure the working tree is clean:
   ```bash
   git status --porcelain
   ```
   If non-empty, stop and report: "Uncommitted changes detected — please stash or commit them first."

2. Pull latest `main`:
   ```bash
   git checkout main && git pull --ff-only origin main
   ```

3. Build the branch name with this exact format:
   ```
   <github-username>/<LABEL>-<title-kebab>
   ```
   - `github-username` = `gh api user --jq .login`
   - `LABEL` = the issue label prefix, uppercased (e.g. `MG-011`)
   - `title-kebab` = title minus the `LABEL:` prefix, lowercased, spaces & punctuation → hyphens, capped at ~50 chars

   Example: `benabdou1001/MG-011-per-route-boundaries-deploy`

4. Create and switch:
   ```bash
   git checkout -b <branch-name>
   ```

5. Confirm: `✅ Branch <branch-name> created from main.`

---

## Step 3 — Move the issue to "In progress"

```bash
ITEM_ID=$(gh api graphql -f query='
  query {
    organization(login: "Mayda-enigma") {
      projectV2(number: 1) {
        items(first: 200) {
          nodes { id content { ... on Issue { number } } }
        }
      }
    }
  }' | jq -r --argjson n <num> '.data.organization.projectV2.items.nodes[] | select(.content.number == $n) | .id')

gh project item-edit \
  --project-id PVT_kwDOERkXVs4BYgAL \
  --id "$ITEM_ID" \
  --field-id PVTSSF_lADOERkXVs4BYgALzhTlc34 \
  --single-select-option-id 47fc9ee4
```

Save `$ITEM_ID` — reused in Step 8.

If `$ITEM_ID` is empty (issue not on the board), keep going with the code work and flag it in the final output.

---

## Step 4 — Work through the task list

Process every task from the parsed list **in order**, one at a time. Run this cycle for each:

### 4a. Announce

```
🔨 [N/Total] <task>
```

### 4b. Implement

- Read referenced files first. Mirror existing patterns — the issue almost always points to a pattern folder; follow it closely.
- Stay within scope. Don't refactor adjacent code.
- Respect explicit tech constraints in the issue body (no hex colors, naming conventions, design tokens, etc.).
- If a task depends on a prior task's output, that prior commit must already exist.

### 4c. Commit

```bash
git add -A
git commit -m "[<LABEL>] <concise summary>"
```

- Subject under 72 chars. Derive from the task — don't copy verbatim.
- Never use `--no-verify`. If a hook fails, fix the root cause and create a new commit.

### 4d. Confirm

```
✅ [N/Total] Committed: [<LABEL>] <summary>
```

**One commit per task. No batching. No skipping.**

---

## Step 5 — Acceptance criteria check

Walk every item in the issue's **Acceptance criteria** section:

- ✅ Met — note briefly how.
- ❌ Not met — fix it, then commit: `[<LABEL>] <fix description>`.

Do not advance until every criterion is ✅.

---

## Step 6 — Quality gate

Detect the stack from the repo and run lint → build → tests in that order. Common patterns:

- **Node** (`package.json` + lockfile): try `pnpm`, fall back to `npm`/`yarn`.
  - `pnpm lint && pnpm build && pnpm test`
- **Python** (`pyproject.toml`/`requirements.txt`): use whatever the repo configures.
  - `ruff check . && pytest` (or the equivalent declared in the repo)

For each command:
1. Run it.
2. If it fails, fix the errors and commit with a dedicated message:
   - `[<LABEL>] Fix lint errors`
   - `[<LABEL>] Fix build errors`
   - `[<LABEL>] Fix failing tests`

Hard requirement: lint + build + tests green before opening the PR.

For UI changes, also start the dev server and click through the affected flow. If you can't run the UI here, say so explicitly — do not claim success.

---

## Step 7 — Push and open the pull request

```bash
git push -u origin HEAD

gh pr create \
  --base main \
  --title "[<LABEL>] <Issue Title>" \
  --body "$(cat <<'EOF'
## Summary
<one or two sentences describing what this PR does>

## Changes
- <bullet per task group / per significant change>

## Acceptance criteria
- [x] <criterion 1>
- [x] <criterion 2>

## How to test
- <route to visit / endpoint to hit / button to click>
- <expected outcome>

---
Closes #<num>
EOF
)"
```

Print and save the PR URL.

---

## Step 8 — Move the issue to "In review"

```bash
gh project item-edit \
  --project-id PVT_kwDOERkXVs4BYgAL \
  --id "$ITEM_ID" \
  --field-id PVTSSF_lADOERkXVs4BYgALzhTlc34 \
  --single-select-option-id df73e18b
```

---

## Final output

```
╔══════════════════════════════════════════════╗
║          ✅  work-issue complete              ║
╠══════════════════════════════════════════════╣
║  Issue   : <LABEL> — <Title>                 ║
║  Branch  : <branch-name>                     ║
║  Commits : <N>                               ║
║  PR      : <PR URL>                          ║
║  Status  : In review                         ║
╚══════════════════════════════════════════════╝
Waiting for review. I have not merged anything.
```

If more issue numbers remain in `$ARGUMENTS`, `git checkout main` and restart from Step 1 with the next one.

---

## Hard rules

- **Never merge the PR.** Wait for explicit user approval.
- **Never push directly to `main`. Never force-push.**
- **One commit per task** — no batching, no exceptions.
- **Always read before writing** — check referenced pattern files first.
- **Never skip pre-commit hooks** (no `--no-verify`, no `-c commit.gpgsign=false`).
- **No hex colors or magic values** if the codebase has a token system — follow it.
- If blocked (ambiguous task, missing dep, broken env), stop and explain — do not improvise.
- If the issue isn't on the project board, do the code work anyway and flag at the end.
