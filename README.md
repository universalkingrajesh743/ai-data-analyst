# 🧠 Agentic AI Business Intelligence Copilot

> Enterprise-grade conversational analytics platform — ask anything about your data in plain English and get SQL, charts, forecasts, root cause analysis, and actionable insights instantly.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-green)
![Streamlit](https://img.shields.io/badge/Streamlit-Frontend-red)
![LangChain](https://img.shields.io/badge/LangChain-Agentic-purple)
![Groq](https://img.shields.io/badge/LLM-Groq%20LLaMA%203.3-orange)
![Docker](https://img.shields.io/badge/Docker-Ready-blue)

---

## 💡 Problem

Non-technical users cannot query databases. Business analysts waste hours
writing SQL or waiting for data teams. Executives need instant answers.
This platform solves all three with a multi-agent AI system.

---

## 🚀 Live Demo

🔗 **[your-username-ai-data-analyst.streamlit.app](https://streamlit.app)**

---

## ✨ Feature Matrix

| Feature | Description | Agent |
|---|---|---|
| 🗣️ Natural Language → SQL | Ask in plain English, get SQL + results | SQL Agent |
| 🛡️ Query Validation | Blocks DROP/DELETE/injection attempts | Validator Agent |
| 📊 Auto Chart Selection | Picks bar/line/pie/scatter automatically | Visualization Agent |
| 💡 AI Insight Generation | Explains why the data looks that way | LLM Agent |
| 🧠 Session Memory | Remembers previous questions for context | Memory Agent |
| 🔄 Auto SQL Retry | Fixes failed queries with error context | SQL Agent |
| 📈 ML Forecasting | Predicts next N months with Prophet | Forecasting Agent |
| 🔬 Data Quality Scan | Detects nulls, duplicates, outliers | Quality Agent |
| 📊 Auto Dashboard | One-click KPI dashboard generation | Dashboard Agent |
| 🔎 Root Cause Analysis | AI investigates why a metric dropped | RCA Agent |
| ⚡ Query Optimizer | Performance suggestions + index hints | Optimizer Agent |
| 🚨 Business Alerts | Revenue drops, high returns, discounts | Alerting Agent |
| 📂 Multi-DB Support | Upload any SQLite or PostgreSQL DB | Connector |
| 📄 PDF Report Export | Full session report with charts + SQL | Report Generator |
| ⬇️ CSV Export | Download any query result | Export |

---

## 🧠 Multi-Agent Architecture

User (Plain English Question)

↓

Streamlit Chat UI

↓

FastAPI Backend

↓

┌────────────────────────────────────────┐

│           Agent Orchestrator           │

│                                        │

│  Validator  →  SQL Agent  →  Optimizer │

│      ↓             ↓                   │

│  Quality       Forecaster              │

│  Agent             ↓                   │

│      ↓         Root Cause              │

│  Dashboard     Alerting                │

│  Agent         Agent                   │

└────────────────────────────────────────┘

↓

Groq LLaMA 3.3 (Free LLM)

↓

SQLite / PostgreSQL

↓

Results + Charts + Insights + PDF

---

## 🧰 Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | Streamlit | Chat UI + tabs + charts |
| Backend | FastAPI + Python 3.11 | REST API + agent orchestration |
| LLM | Groq LLaMA 3.3 70B | SQL generation + insights |
| Agent Framework | LangChain | Memory + message handling |
| Forecasting | Facebook Prophet | Time-series ML forecasting |
| Charts | Plotly Express | Auto-generated visualizations |
| Database | SQLite + PostgreSQL | Multi-database support |
| Memory | SQLite-backed store | Conversation history |
| PDF Export | fpdf2 | Session report generation |
| Deployment | Docker + Streamlit Cloud | Containerized deployment |

---

## 🗂️ Project Structure
ai-data-analyst/

├── agent/

│   ├── sql_agent.py          # Core LLM → SQL pipeline

│   ├── validator.py          # Query safety validation

│   ├── memory.py             # Session memory + query log

│   ├── forecaster.py         # Prophet ML forecasting

│   ├── data_quality.py       # Data quality scanner

│   ├── dashboard.py          # Auto dashboard generator

│   ├── root_cause.py         # Root cause analysis

│   ├── optimizer.py          # Query optimization hints

│   ├── alerting.py           # Business alerts engine

│   └── report_generator.py   # PDF report generator

├── api/

│   └── routes.py             # All FastAPI endpoints

├── app/

│   └── streamlit_app.py      # Full Streamlit UI (8 tabs)

├── database/

│   ├── schema.py             # SQLAlchemy table definitions

│   └── seed_data.py          # Sample data seeder

├── .streamlit/

│   └── config.toml           # Streamlit theme config

├── main.py                   # FastAPI entry point

├── Dockerfile                # Docker container config

├── docker-compose.yml        # Multi-service deployment

├── requirements.txt

└── .env.example

---

## ⚡ Quick Start (Local)

### 1. Clone
```bash
git clone https://github.com/YOUR_USERNAME/ai-data-analyst.git
cd ai-data-analyst
```

### 2. Environment
```bash
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux

pip install -r requirements.txt
```

### 3. API Key
```bash
cp .env.example .env
# Add your free Groq key from console.groq.com
```

### 4. Seed database
```bash
python -m database.seed_data
```

### 5. Run
```bash
# Terminal 1
python main.py

# Terminal 2
streamlit run app/streamlit_app.py
```

Open `http://localhost:8501`

---

## 🐳 Quick Start (Docker)

```bash
# Add your key to .env first
echo "GROQ_API_KEY=gsk_your_key" > .env

docker-compose up --build
```

Open `http://localhost:8501`

---

## 🔌 REST API

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/query` | NL → SQL → Results |
| POST | `/api/report/pdf` | Generate PDF report |
| POST | `/api/upload-db` | Upload SQLite database |
| POST | `/api/root-cause` | Root cause analysis |
| POST | `/api/optimize` | Query optimization |
| GET | `/api/forecast` | ML sales forecast |
| GET | `/api/dashboard` | Auto dashboard data |
| GET | `/api/quality` | Data quality scan |
| GET | `/api/alerts` | Business alerts |
| GET | `/api/schema` | Database schema |
| GET | `/api/history` | Query history |
| GET | `/api/health` | Health check |

Interactive API docs: `http://localhost:8000/docs`

---

## 💬 Example Queries
Show me the sales drop in Odisha in Q3 2024

Which product category has the highest revenue?

Monthly revenue trend for 2024

Compare online vs retail vs wholesale channels

Who are the top 3 sales reps by revenue?

Predict next 6 months revenue for Odisha

Why did sales drop in Q3 2024?

Show revenue breakdown by category as percentage

---

## 📄 License

MIT — free to use and modify.