# 00_REQUIREMENTS.md

## System Requirements for Bot Refactoring

### Core Principles

1. **Full Migration to FastAPI**: Migrate `bot_barca.py` to a FastAPI-based architecture.
2. **Pydantic Configuration**: Enforce Pydantic v2.10+ with `ConfigDict(strict=True)` in `src/shared/config.py`.
3. **Zero-Dead-Code Policy**: All legacy code from `bot_barca.py` must be removed after migration.
4. **Local Inference**: The sports summary agent will use `qwen3:30b` via the local compatibility API endpoint `/v1`.