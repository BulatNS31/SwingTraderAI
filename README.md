# SwingTraderAI 📈

Smart technical analysis for MOEX and crypto traders. Receive instant reports and signals on stocks (Moscow Exchange) and cryptocurrencies.

* **Market Insights:** Trend analysis, key levels, overbought/oversold detection.
* **Automation:** Automatic notifications for your watchlist.
* **Flexibility:** Easy setup and extension via code.

---

## 🚀 Features

- **Multi-Source Data:**
  - **MOEX:** via `yfinance` (tickers like `SBER.ME`, `GAZP.ME`, `IMOEX.ME`).
  - **Crypto:** via `ccxt` (Binance, Bybit, OKX, etc.).
- **Technical Engine:** Calculates 50+ indicators using `pandas_ta`.
- **AI-Powered Reasoning:** Uses **LangGraph** + LLMs (Claude, GPT, Gemini) to interpret market context.
- **Persistent Storage:** Full history of analyses and signals in PostgreSQL.
- **Alert System:** Instant Telegram notifications for trade setups.
- **Hybrid Approach:** Classic rule-based signals + multi-step LLM reasoning.

---

## 🏗 Architecture

```text
swingtraderai/
├── app/                # Core FastAPI backend
│   ├── core/           # Config, database, scheduler
│   ├── models/         # SQLAlchemy models
│   ├── schemas/        # Pydantic schemas
│   ├── services/       # Data fetcher, indicators, LLM agent
│   ├── tasks/          # Background jobs (market scanner)
│   └── api/            # HTTP endpoints
├── bots/               # Client implementations
│   └── telegram/       # aiogram bot
├── alembic/            # Database migrations
├── tests/              # Test suite (pytest)
└── scripts/            # CLI utilities

```

---

## 🏗 Implemented Architecture: API → Services → Repositories → DB + Multi-Tenancy
We have successfully migrated the project to a clean, layered architecture:

* API Layer (api/v1/routers/) — Handles HTTP requests, validation, and dependencies
* Service Layer (services/) — Contains business logic, rules, calculations, and orchestration
* Repository Layer (repositories/) — Responsible for all database operations and queries
* Database Layer — SQLAlchemy models + Alembic migrations

Key Multi-Tenancy Features:
* All user-specific data is isolated using tenant_id
* Automatic tenant filtering is implemented in BaseRepository
* tenant_id is extracted from JWT token via get_current_tenant_id()
* Shared data (Ticker, MarketData, Exchange) remains tenant-independent
* Row Level Security (RLS) is prepared at the database level

---

## 🛠 Tech Stack

* **Python:** 3.12 - 3.14
* **Web:** FastAPI, Uvicorn, httpx
* **Database:** SQLAlchemy 2.0, Alembic, PostgreSQL, Redis
* **AI/ML:** LangGraph, LangChain, pandas, numpy
* **Trading:** ccxt, yfinance, pandas_ta
* **Bot:** aiogram 3.x
* **Task Management:** APScheduler, Celery

---

## ⚙️ Quick Start

1. **Clone & Install**
```bash
git clone https://github.com/David2261/SwingTraderAI.git
cd SwingTraderAI
poetry install

```


2. **Environment**
Create a `.env` file based on the template:
```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/ta_db
TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN
ANTHROPIC_API_KEY=sk-ant-...

```


3. **Infrastructure**
```bash
docker run -d --name ta-postgres -e POSTGRES_PASSWORD=password -p 5432:5432 postgres:16
alembic upgrade head

```


4. **Run**
```bash
uvicorn swingtraderai.main:app --reload # --port 7123

python -m bots.telegram.bot

```



---

## 🧪 Development & Quality Control

We use a strict set of tools to ensure code quality. All tools are located in the `test` dependency group.

### Static Analysis & Formatting

| Tool | Purpose | Command |
| --- | --- | --- |
| **Ruff** | Ultra-fast Linter & Sorting imports | `poetry run ruff check . --fix` |
| **Black** | Uncompromising code formatter | `poetry run black .` |
| **Mypy** | Static type checking | `poetry run mypy .` |

### Running Tests

To run the test suite using `pytest`:

```bash
poetry run pytest

```

### CI/CD Simulation

Before pushing your code, it is recommended to run the full checkup:

```bash
poetry run black . && poetry run ruff check . --fix && poetry run mypy .
pre-commit run --all-files

```

---

## 📄 License

Licensed under the **Apache License 2.0**. See `LICENSE` for more information.

```
