# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🚀 Common Commands

- **Start the bot**: `python main.py`
- **Run all tests**: `pytest`
- **Run a single test**: `pytest tests/test_name.py::test_function_name -v`
- **Run tests with coverage**: `pytest --cov=./`
- **Install dependencies**: `pip install -r requirements.txt`
- **Check formatting**: `ruff check .` (if configured) or rely on CI
- **View logs**: Tail the `logs/` directory or use Telegram `/logs` command

## 🏗️ Project Architecture

The codebase follows a modular structure separating concerns:

1. **Entry Point**: `main.py` – orchestrates the bot lifecycle, handles reboot signals, and manages the main loop.
2. **Browser Layer** (`browser/`): 
   - `controller.py`: Manages Playwright browser lifecycle and navigation.
   - `auth.py`: Handles login, session persistence, and console session detection.
   - `navigator.py`: Interacts with the Transfer Market UI (navigation, filtering).
   - `detector.py`: Scans and parses listing data from the web page.
   - `relist.py`: Executes relisting actions (price adjustment, duration, etc.).
   - `rate_limiter.py`: Implements randomized delays to avoid detection.
   - `session_keeper.py`: Monitors session health and triggers re-login if needed.
3. **Core Logic** (`logic/`):
   - `relist_engine.py`: Implements the Golden Hours logic and cycle processing (hold windows, timed relists).
   - `notification_batch.py`: Batches Telegram notifications to avoid spamming.
4. **State Management**:
   - `bot_state.py`: Thread-safe state holder for reboot flags, Telegram commands, and statistics.
5. **External Integrations**:
   - `telegram_handler.py`: Handles bidirectional communication with Telegram (commands, alerts).
   - `notifier.py`: Sends one-off alerts (used at startup).
6. **Configuration** (`config/`):
   - `config.py`: Typed configuration schema with validation and environment variable binding.
   - `log_config.py`: Sets up logging configuration.
7. **Handlers**:
   - `sold_handler.py`: Processes sold item detection and credit collection.
8. **Testing** (`tests/`): Unit and integration tests using pytest.

## ⚙️ Configuration

- Configuration is loaded from `config.json` (created on first run if missing).
- Environment variables override specific values (e.g., `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`, `FIFA_EMAIL`, `FIFA_PASSWORD`).
- Use `python -c "from config.config import ConfigManager; print(ConfigManager().load())"` to view current config.

## 🧪 Testing

- Tests live in the `tests/` directory and follow pytest conventions.
- Mock external services (Telegram, browser) where appropriate.
- Run specific test suites: `pytest tests/test_golden_hour.py` for Golden Hours logic.

## 🔑 Key Points for Development

- The bot is designed to run 24/7 with automatic recovery from crashes and session expirations.
- Golden Hours logic (`logic/relist_engine.py`) is central: it holds relists until specific windows (16:10, 17:10, 18:10) then executes them in batch.
- Telegram commands are processed via `bot_state.py` and handled in the main loop (`main.py`).
- All browser interactions use Playwright with careful rate limiting to avoid detection.
- Configuration validation occurs at load time via `__post_init__` in dataclasses (`config.py`).
- **Always check `.planning/STATE.md` at startup for current project activity and recent updates**

## 🛠️ Orchestrator Configuration
The project uses an orchestrator to route requests to specialized sub‑agents. The mapping is stored in `C:\Users\Ebby\.claude\agents/orchestrator.md` where each intent (`debug`, `review`, `test`, `feature`, `docs`) maps to a `subagent_type` and a prompt file. See `C:\Users\Ebby\.claude\agents/orchestrator.md` for details.