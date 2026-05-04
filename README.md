# Helix SROP — RAGASUDHA S S

## Setup

```bash
git clone <your-repo>
cd helix-srop
# Assuming uv is installed, otherwise use pip
pip install -r requirements.txt 
cp .env.example .env  # fill in GEMINI_API_KEY
python -m app.rag.ingest --path docs/
uvicorn app.main:app --reload
```

## Quick Test

```bash
SESSION=$(curl -s -X POST localhost:8000/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{"user_id": "u_demo", "plan_tier": "pro"}' | jq -r .session_id)

curl -s -X POST localhost:8000/v1/chat/$SESSION \
  -H "Content-Type: application/json" \
  -d '{"message": "How do I rotate a deploy key?"}' | jq .
```

## Architecture

```text
POST /v1/chat/{session_id}
         │
         ▼
┌─────────────────────────┐
│  SROP Pipeline          │
│  1. Load session state  │
│  2. Run ADK orchestrator│
│  3. Save updated state  │
│  4. Write trace to DB   │
└────────────┬────────────┘
             │ routes via ADK AgentTool
       ┌─────┴──────┐
       ▼            ▼
 KnowledgeAgent  AccountAgent
 (RAG + search)  (DB tools)
       │
  Vector store    App DB
  (doc chunks)  (sessions, traces)
```

## Design Decisions

### State persistence (which pattern and why)
I used **Pattern 3** from the ADK guide because it is the most lightweight and reliable approach. Instead of persisting the full ADK session object (which can be bulky), I only store the essential `SessionState` in SQLite. On each turn, this state is loaded and injected into the agent's instruction, ensuring that context like `user_id` and `plan_tier` is always available even after a server restart.

### Chunking strategy
I used **fixed-size token chunking** (500 tokens with 50-token overlap) because it aligns perfectly with LLM context window semantics. Token-based chunking ensures that each context piece is small enough for high-precision retrieval while the overlap prevents loss of meaning at the boundaries.

### Vector store choice
I chose **ChromaDB** because it provides a simple, persistent, and local-first vector store experience. It integrates seamlessly with Python and allows the project to be fully self-contained without requiring external cloud database setup.

## Known Limitations
- The `AccountAgent` uses mock data for builds and account status as per the assignment scope.
- Rate limits on the Gemini free tier can occasionally cause 429 errors during high-frequency testing.

- Implement **E3: Streaming SSE** for better UI responsiveness.
- Add more comprehensive unit tests for edge cases in the pipeline.

## Time Spent

| Phase | Time |
|-------|------|
| Setup + DB + FastAPI boilerplate | 30 min |
| RAG ingest + search_docs | 45 min |
| ADK agents | 45 min |
| pipeline.py + state persistence | 40 min |
| Escalation Agent (E2) | 20 min |
| Eval Harness (E7) | 15 min |
| Tests | 25 min |
| README | 15 min |
| **Total** | **3h 55m** |

## Extensions Completed
- [ ] E1: Idempotency
- [x] E2: Escalation agent
- [ ] E3: Streaming SSE
- [ ] E4: Reranking
- [x] E5: Guardrails
- [x] E6: Docker
- [x] E7: Eval harness


