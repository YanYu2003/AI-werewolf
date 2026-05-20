# 🐺 AI Werewolf

**Multi-agent role-playing game** — werewolf killing with LLM-powered AI agents.

8 players (2 werewolves, 1 seer, 1 witch, 1 hunter, 3 villagers) controlled by LLM agents, with optional human player participation. Real-time spectating via WebSocket, replay system, and a React frontend.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10, FastAPI, Uvicorn, Pydantic |
| Frontend | React 18, TypeScript, Vite |
| AI Agent | LLM-driven agent (pluggable) |
| Real-time | WebSocket (FastAPI native) |
| Data | In-memory game engine |

---

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\pip install fastapi==0.109.2 starlette==0.37.0 pydantic==2.6.1 uvicorn pytest
.venv\Scripts\python -m uvicorn app.main:app --port 8000
```

Server at `http://127.0.0.1:8000`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App at `http://localhost:5173`. Dev server proxies `/api` and `/ws` to backend.

---

## Architecture

```
backend/app/
├── api/              # REST + WebSocket
│   ├── routes_games.py    # 9 endpoints
│   └── websocket.py       # WS /ws/games/{id}
├── agents/           # LLM agents
│   ├── base.py
│   ├── werewolf_agent.py
│   ├── seer_agent.py
│   ├── witch_agent.py
│   ├── hunter_agent.py
│   └── villager_agent.py
├── engine/           # Game logic
│   ├── game_engine.py     # Core loop
│   ├── action_validator.py
│   └── visibility.py      # Info hiding
├── services/         # API services
│   ├── game_runner.py
│   ├── public_state_service.py
│   └── websocket_manager.py
└── schemas/          # Pydantic models

frontend/src/
├── pages/            # HomePage, GamePage, ReplayPage
├── components/       # PlayerBoard, EventTimeline, HumanActionPanel, ...
├── api/              # REST + WS clients
└── types/            # TypeScript interfaces
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Health check |
| POST | `/api/games` | Create game |
| GET | `/api/games` | List games |
| GET | `/api/games/{id}/state` | Public state |
| GET | `/api/games/{id}/players/{pid}/view` | Private view |
| POST | `/api/games/{id}/step` | Advance one step |
| POST | `/api/games/{id}/auto-run` | Auto-complete |
| POST | `/api/games/{id}/players/{pid}/actions` | Human action |
| GET | `/api/games/{id}/logs` | Safe logs |
| GET | `/api/games/{id}/replay` | Replay data |
| WS | `/ws/games/{id}` | Real-time events |

---

## Testing

```bash
.venv\Scripts\python -m pytest backend/tests/ -q
# 117 tests, Phase 1–3 + LLM
```

---

## LLM Agent (Optional)

By default, all AI agents use **heuristic (rule-based)** strategies. The system also supports **LLM-driven agents** via any OpenAI-compatible API.

### Enable LLM

1. Copy `.env.example` to `.env` and fill in:
   ```
   LLM_ENABLED=true
   LLM_API_KEY=sk-your-key-here
   LLM_BASE_URL=https://api.openai.com/v1   # Or any OpenAI-compatible endpoint
   LLM_MODEL=gpt-4o-mini
   ```

2. When enabled, agents prioritize LLM-generated decisions. If the LLM returns invalid JSON, times out, or returns an illegal action, the system automatically **falls back** to the heuristic agent.

### Security

- LLM only receives a **safe AgentView** — never the full `GameState`.
- Hidden roles are never passed to the LLM.
- The LLM output is parsed by `action_validator` before execution.
- No API keys are logged or written to reports.

---

## License

MIT
