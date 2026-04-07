# Plan: Remediate GitHub Secret Scanning Violation

## Problem
GitHub rejected a push due to Secret Scanning detecting credentials in `token.json.backup`. The file is currently tracked by Git and was included in a recent commit.

## Current State
- `.gitignore` already includes `token.json` but NOT `token.json.backup`
- `token.json.backup` exists in workspace and is likely tracked
- Merge conflict in `log_partidos.md` between "Updated upstream" and "Stashed changes"
- A problematic commit containing the secret is in the local history

## Objectives
1. Ensure `token.json.backup` and `token.json` are ignored by Git
2. Remove `token.json.backup` from Git tracking
3. Remove the secret from Git history (reset commit)
4. Resolve merge conflict accepting incoming changes
5. Create a clean commit with only safe changes
6. Push successfully

## Detailed Steps

### 1. Add token.json.backup to .gitignore
Edit `.gitignore` and add `token.json.backup` under the "Credenciales y secretos" section after `token.json`.

**Expected change:**
```
# Credenciales y secretos (¡NUNCA SUBIR A GITHUB!)
credentials.json
token.json
token.json.backup
client_secret_*.json
.env
```

### 2. Remove token.json.backup from Git tracking
Run:
```bash
git rm --cached token.json.backup
```

### 3. Reset the problematic commit
Run:
```bash
git reset --soft HEAD~1
```
This will undo the last commit while keeping changes in the staging area.

### 4. Resolve merge conflict in log_partidos.md
Accept incoming changes (Updated upstream) and discard stashed changes.

**Conflict region (lines 357-366):**
```
<<<<<<< Updated upstream
- ✅ Actualizado el 2026-04-07 17:51:33: Calendario sincronizado con Google.
- ✅ Actualizado el 2026-04-07 17:52:50: Calendario sincronizado con Google.
- ✅ Actualizado el 2026-04-07 18:32:01: Calendario sincronizado con Google.
=======
- ✅ Actualizado el 2026-04-07 20:16:17: Calendario sincronizado con Google.
- ✅ Actualizado el 2026-04-07 20:17:46: Calendario sincronizado con Google.
- ✅ Actualizado el 2026-04-07 20:24:40: Calendario sincronizado con Google.
- ✅ Actualizado el 2026-04-07 20:27:43: Calendario sincronizado con Google.
>>>>>>> Stashed changes
```

**Resolution:** Keep the upstream lines (three entries) and delete the conflict markers.

### 5. Stage changes and create new commit
Stage all safe changes (including updated .gitignore and any other code changes):
```bash
git add .
git commit -m "fix: remove secret files from tracking and update .gitignore"
```

### 6. Push to remote
```bash
git push
```

## Notes
- Ensure no other secret files are tracked (check with `git ls-files`).
- After reset, verify the staging area doesn't contain `token.json.backup`.
- If push is rejected due to non-fast-forward, use `git push --force-with-lease` (but only after confirming remote state).

## Risk Mitigation
- The soft reset preserves local changes; no data loss.
- Merge conflict resolution is straightforward; we keep upstream changes.
- Secret will be removed from future commits but may still exist in remote history (requires force push or secret rotation). Since the commit hasn't been pushed yet (rejected), resetting before push will prevent the secret from ever reaching remote.

## Verification
After completing steps:
- `git status` should show no untracked secrets
- `git log --oneline` should show the new commit
- GitHub push should succeed without Secret Scanning warnings.
