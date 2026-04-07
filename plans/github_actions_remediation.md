# GitHub Actions Build Failure Remediation Plan

## Analysis Summary

**Build Failure Details:**
- **Exit Code:** 1 (Process completed with exit code 1)
- **Annotations:** 1 error and 1 warning
- **Critical Deprecation Notice:** Node.js 20 actions are deprecated

**Affected Actions:**
1. `actions/checkout@v4`
2. `actions/setup-python@v4`

**Timeline:**
- Node.js 20 will be forced to run with Node.js 24 by default starting **June 2nd, 2026**
- Node.js 20 will be removed from the runner on **September 16th, 2026**

**Official Migration Guidance:** [GitHub Blog - Deprecation of Node.js 20](https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/)

## Root Cause Analysis

The build failure (exit code 1) could be caused by:
1. **Node.js 20 deprecation warnings** causing action failures
2. **Actual script errors** in `bot_barca.py` (authentication, network issues, etc.)
3. **Dependency installation issues** (requirements.txt vs pyproject.toml mismatch)
4. **Git operations failures** in the commit/push step

## Remediation Plan

### Phase 1: Immediate Fixes for Deprecation Warnings

#### 1. Update GitHub Actions Workflow (`run_bot.yml`)

**Current Configuration:**
```yaml
steps:
  - name: Checkout del código
    uses: actions/checkout@v4

  - name: Configurar Python
    uses: actions/setup-python@v4
```

**Required Changes:**
1. Update `actions/setup-python@v4` → `actions/setup-python@v5` (supports Node.js 24)
2. Keep `actions/checkout@v4` (latest major version, but add environment variable)
3. Add global environment variable: `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true`

**Updated Workflow:**
```yaml
name: Sincronizador Cule Diario

on:
  schedule:
    - cron: '0 * * * *'
  workflow_dispatch:

env:
  # Proactively migrate to Node.js 24 to avoid deprecation warnings
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - name: Checkout del código
        uses: actions/checkout@v4

      - name: Configurar Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'

      - name: Instalar dependencias
        run: pip install -r requirements.txt

      - name: Ejecutar script del Barça y Sincronizar Google Calendar
        env:
          GOOGLE_TOKEN_JSON: ${{ secrets.GOOGLE_TOKEN_JSON }}
        run: python bot_barca.py

      - name: Hacer commit y push (Pintar de verde)
        run: |
          git config --global user.name "Aleix Quirante"
          git config --global user.email "quirante70@gmail.com"
          git add log_partidos.md
          git commit -m "⚽ Barça Bot: Sincronización diaria completada $(date +'%Y-%m-%d')" || exit 0
          git push
```

### Phase 2: Diagnose and Fix Exit Code 1

#### 2.1 Check for Actual Build Errors
- Review GitHub Actions logs for the specific error message
- Test `bot_barca.py` locally to identify runtime issues
- Verify `GOOGLE_TOKEN_JSON` secret is properly configured

#### 2.2 Update Dependencies
**Current `requirements.txt`:**
```
requests
icalendar
google-api-python-client
google-auth-httplib2
google-auth-oauthlib
beautifulsoup4
lxml
```

**Missing from `pyproject.toml` dependencies:**
- pydantic>=2.10
- pydantic-settings>=2.5
- httpx>=0.27
- cachetools>=5.3
- feedparser>=6.0
- openai>=1.0

**Action:** Update `requirements.txt` to match `pyproject.toml` or install from `pyproject.toml` directly.

#### 2.3 Improve Error Handling
Add better error handling to the workflow:
```yaml
- name: Ejecutar script del Barça y Sincronizar Google Calendar
  env:
    GOOGLE_TOKEN_JSON: ${{ secrets.GOOGLE_TOKEN_JSON }}
  run: |
    set -e  # Exit immediately on error
    python bot_barca.py || {
      echo "Script failed with exit code $?"
      exit 1
    }
```

### Phase 3: Testing and Verification

#### 3.1 Test Locally
```bash
# Create test environment
python -m venv test_env
source test_env/bin/activate
pip install -r requirements.txt

# Test script execution
GOOGLE_TOKEN_JSON=$(cat token.json) python bot_barca.py
```

#### 3.2 Test in GitHub Actions
1. Create a test branch with the updated workflow
2. Trigger manual workflow run via `workflow_dispatch`
3. Monitor execution and verify no deprecation warnings
4. Confirm exit code 0 (success)

#### 3.3 Monitor for 24 Hours
- Verify scheduled runs complete successfully
- Check `log_partidos.md` for updates
- Confirm Google Calendar synchronization works

## Migration Diagram

```mermaid
flowchart TD
    A[Build Failure<br>Exit Code 1] --> B[Analyze Logs]
    B --> C{Identify Issues}
    C --> D[Node.js 20 Deprecation]
    C --> E[Script Execution Error]
    
    D --> F[Update Actions]
    F --> F1[setup-python@v4 → v5]
    F --> F2[Add FORCE_JAVASCRIPT_ACTIONS_TO_NODE24]
    
    E --> G[Debug Script]
    G --> G1[Check Dependencies]
    G --> G2[Verify Secrets]
    G --> G3[Test Locally]
    
    F --> H[Update Workflow]
    G --> H
    
    H --> I[Test in GitHub]
    I --> J{Success?}
    J -->|Yes| K[Deploy to Main]
    J -->|No| G
    
    K --> L[Monitor Scheduled Runs]
```

## Rollback Plan

If the updated workflow fails:
1. Revert to previous working version
2. Temporarily add `ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION=true` (opt-out of Node.js 24)
3. Investigate specific compatibility issues

## Success Criteria

1. ✅ No Node.js 20 deprecation warnings in build logs
2. ✅ Build completes with exit code 0 (success)
3. ✅ All workflow steps execute without errors
4. ✅ Google Calendar synchronization works
5. ✅ `log_partidos.md` is updated with commit

## Next Steps

1. **Immediate:** Switch to Code mode to implement workflow updates
2. **Short-term:** Test the updated workflow in a branch
3. **Long-term:** Consider migrating from `requirements.txt` to `pyproject.toml` for dependency management
4. **Monitoring:** Set up notifications for workflow failures