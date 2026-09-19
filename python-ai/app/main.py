import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from prometheus_client import Counter, Histogram, make_asgi_app
from .database import init_db, get_session
from .schemas import ChatRequest, ChatResponse, KnowledgeRequest
from .memory import MemoryStore
from .rag import ingest
from .agents import RunContext, run_multi_agent

REQUESTS = Counter("agent_requests_total", "Agent API requests", ["endpoint"])
LATENCY = Histogram("agent_request_seconds", "Agent request latency", ["endpoint"])

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(title="Enterprise Multi-Agent AI Platform", version="1.0.0", lifespan=lifespan)
app.mount("/metrics", make_asgi_app())

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/v1/knowledge")
async def add_knowledge(
    req: KnowledgeRequest,
    x_tenant_id: str = Header(...),
    db: AsyncSession = Depends(get_session),
):
    REQUESTS.labels("knowledge").inc()
    await ingest(db, x_tenant_id, req.documents)
    return {"ingested": len(req.documents)}

@app.post("/v1/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    x_tenant_id: str = Header(...),
    db: AsyncSession = Depends(get_session),
):
    REQUESTS.labels("chat").inc()
    start = time.perf_counter()
    memory = MemoryStore(db)
    try:
        await memory.ensure_conversation(req.session_id, x_tenant_id)
        history = await memory.history(req.session_id)
        await memory.append(req.session_id, "user", req.message)
        answer = await run_multi_agent(
            RunContext(tenant_id=x_tenant_id, db=db), req.message, history)
        await memory.append(req.session_id, "assistant", answer)
        return ChatResponse(session_id=req.session_id, answer=answer)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    finally:
        LATENCY.labels("chat").observe(time.perf_counter() - start)
