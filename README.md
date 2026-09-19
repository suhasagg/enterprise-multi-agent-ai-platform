# Enterprise Multi-Agent AI Platform

A production-oriented polyglot reference architecture for enterprise agentic AI.

## What it demonstrates

- Multi-agent orchestration: supervisor, research, reasoning, execution, review
- OpenAI Agents SDK + Responses API model runtime
- Model Context Protocol (MCP) over Streamable HTTP
- RAG with PostgreSQL/pgvector
- Durable conversation memory
- Human approval for high-risk actions
- Java/Spring Boot enterprise tool service
- Spring AI 2.x MCP server
- Redis caching
- OpenTelemetry-ready services
- Prometheus metrics
- Docker Compose local environment
- Evaluation harness and tests
- Tenant-aware API contracts

## Architecture

```text
Client
  |
  v
Python FastAPI AI Gateway :8000
  |
  +--> Supervisor Agent
        |--> Research Agent --> RAG / Knowledge Base
        |--> Reasoning Agent
        |--> Execution Agent --> Java MCP Server :8081/mcp
        |                       |--> CRM
        |                       |--> Ticketing
        |                       `--> Risky Action (approval)
        `--> Review Agent
  |
  +--> PostgreSQL + pgvector
  `--> Redis

Java Spring Boot Tool Service
  `--> Spring AI MCP Server (Streamable HTTP)
```

## Repository

```text
python-ai/
  app/
    agents.py
    config.py
    database.py
    main.py
    mcp_client.py
    memory.py
    models.py
    rag.py
    schemas.py
  tests/
  requirements.txt

java-tools/
  pom.xml
  src/main/java/com/example/enterpriseai/
  src/main/resources/application.yml

evals/
  dataset.json
  evaluate.py

infra/
  prometheus.yml

docker-compose.yml
.env.example
Makefile
```

## Prerequisites

- Python 3.11+
- Java 21+
- Maven 3.9+
- Docker / Docker Compose
- OpenAI API key

## Quick start

```bash
cp .env.example .env
# set OPENAI_API_KEY

docker compose up --build
```

API:

```bash
curl -X POST http://localhost:8000/v1/chat \
  -H 'Content-Type: application/json' \
  -H 'X-Tenant-Id: acme' \
  -d '{"message":"Research our refund policy and create a support ticket if escalation is required.","session_id":"demo-1"}'
```

Ingest knowledge:

```bash
curl -X POST http://localhost:8000/v1/knowledge \
  -H 'Content-Type: application/json' \
  -H 'X-Tenant-Id: acme' \
  -d '{"documents":[{"id":"refund-policy","text":"Refunds above $500 require manager approval.","metadata":{"source":"policy"}}]}'
```

## Agent design

The supervisor delegates research and reasoning. Execution is isolated behind MCP rather than giving the LLM direct database/service credentials. A reviewer performs a final consistency pass.

This sample deliberately keeps authorization simple. In production replace `X-Tenant-Id` trust with OIDC/JWT validation (for Microsoft environments, Entra ID), use managed identities/secrets, add per-tool authorization and require human approval for irreversible actions.

## Why both Python and Java?

Python owns the AI plane because the current agent ecosystem is richest there. Java owns enterprise actions and MCP exposure, demonstrating how an existing Spring estate can become safely callable by agents.

## Production extensions

- Azure AI Search or managed vector database
- Microsoft Foundry / Azure OpenAI model provider
- Entra ID and workload identity
- Kafka/Event Hubs for long-running workflows
- Durable workflow/checkpoint store
- Kubernetes/AKS + autoscaling
- OpenTelemetry Collector
- Prompt-injection scanning
- DLP/PII redaction
- Policy engine (OPA)
- per-tool approval policy
- offline + online eval dashboards


---

# Engineering Guide

## 1. Executive Architecture View

**Purpose.** Coordinates supervisor, research, reasoning, execution and review agents around tenant-scoped RAG and governed Java MCP tools.

The repository deliberately separates **probabilistic AI reasoning** from **deterministic enterprise controls**. Model outputs may propose plans, rank evidence, summarize observations or choose among permitted tools, but identity, tenancy, authorization, approval, idempotency, rate limits and destructive-action boundaries belong to ordinary software.

### Control Plane vs Data / Action Plane

| Plane | Responsibilities |
|---|---|
| AI / Control Plane | Request interpretation, planning, routing, model invocation, agent coordination, evaluation hooks |
| Context Plane | Retrieval, memory, telemetry, documents, evidence and provenance |
| Policy Plane | Tenant context, RBAC/scopes, risk classification, approval and quotas |
| Action Plane | Narrow Java APIs/MCP tools that perform enterprise operations |
| State Plane | PostgreSQL/pgvector and Redis where used |
| Observability Plane | Metrics, traces, audit events, health and evaluation evidence |

### Trust Boundaries

```text
Untrusted user/content
        |
        v
API validation / identity
        |
        v
AI reasoning boundary
        |
        v
Policy + tool schema boundary
        |
        v
MCP / Java action boundary
        |
        v
Enterprise systems / durable state
```

A production implementation should assume that user prompts, retrieved documents, tool outputs and model-generated arguments can all be hostile or malformed.

## 2. Repository Structure

```text
.env.example
.gitignore
Makefile
README.md
docker-compose.yml
docs/
  ARCHITECTURE.md
evals/
  dataset.json
  evaluate.py
infra/
  prometheus.yml
java-tools/
  Dockerfile
  pom.xml
  src/
    main/
    test/
python-ai/
  Dockerfile
  app/
    __init__.py
    agents.py
    config.py
    database.py
    main.py
    memory.py
    models.py
    rag.py
    schemas.py
  requirements.txt
  tests/
    test_api.py
```

## 3. End-to-End Request Lifecycle

1. **Ingress** — validate request shape, establish tenant/principal context and attach a correlation id.
2. **Context assembly** — load only the memory, documents, telemetry or metadata required for the task.
3. **AI decision** — invoke the configured model/agent using structured contracts where possible.
4. **Policy decision** — independently check tool/model entitlement, risk, tenant and approval requirements.
5. **Execution** — invoke a narrow downstream API or MCP tool with bounded timeout/retry behavior.
6. **Verification** — validate tool result, citations, tests, health signals or other task-specific evidence.
7. **Persistence** — store durable domain state and minimal audit/evaluation evidence.
8. **Response** — return a stable API contract without leaking provider credentials or internal secrets.

## 4. API Surface

| Method | Endpoint | Service |
|---|---|---|
| `GET` | `/health` | Python API |
| `POST` | `/v1/knowledge` | Python API |
| `POST` | `/v1/chat` | Python API |

MCP tools form a separate typed API surface. The Java tool classes and Python MCP client/runtime are the authoritative definitions for those schemas.

## 5. Configuration

```bash
cp .env.example .env
```

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | Runtime configuration |
| `OPENAI_MODEL` | Runtime configuration |
| `DATABASE_URL` | Runtime configuration |
| `REDIS_URL` | Runtime configuration |
| `JAVA_MCP_URL` | Runtime configuration |
| `EMBEDDING_MODEL` | Runtime configuration |
| `LOG_LEVEL` | Runtime configuration |

Use a secrets manager or workload identity in production. Never place long-lived service credentials inside prompts, model instructions or model-visible tool arguments.

## 6. Local Development

```bash
docker compose up --build
```

Useful test commands:

```bash
make python-test
make java-test
```

If a target is not defined in the Makefile, run `pytest` in the Python service and `mvn test` in the Java service.

## 7. Reliability Engineering

Production hardening should include:

- Explicit deadlines for model, database, MCP and downstream calls.
- Bounded retries with exponential backoff and jitter.
- Idempotency keys for every mutation that may be retried.
- Circuit breaking for unhealthy providers or downstream services.
- Cancellation propagation for abandoned requests.
- Concurrency limits to prevent retry storms and resource exhaustion.
- Persistent evidence for ambiguous failures where the caller cannot know whether a side effect committed.
- Schema/version compatibility checks between Python and Java boundaries.
- Graceful degradation when optional AI capabilities are unavailable.

## 8. Security & Governance

- Replace development tokens with OAuth/OIDC or workload identity.
- Validate tenant authorization at **every** storage and action boundary.
- Give agents narrow tools rather than unrestricted database/shell/cloud credentials.
- Treat RAG documents, webpages, images and tool results as untrusted data.
- Add enterprise DLP/PII controls; regex examples are not a complete DLP solution.
- Enforce egress allowlists and SSRF protection in connector services.
- Require human approval and separation of duties for high-impact actions.
- Redact secrets and sensitive payloads from traces.
- Export audit events to immutable/WORM storage when compliance requires it.

## 9. Observability

Correlate the following with a request/workflow/task/incident id:

| Signal | Examples |
|---|---|
| AI | model/provider, latency, tokens, tool calls, retries |
| Retrieval | query latency, candidate count, rerank latency, citations |
| Tools | tool name, decision, latency, success/failure, approval wait |
| Platform | HTTP latency, DB latency, queue depth, Redis errors |
| Business | task success, incident recovery, workflow completion, eval gate |
| Cost | input/output tokens, model cost, tool/infrastructure cost |

Do not log raw prompts or documents by default when they can contain confidential information.

## 10. Testing Strategy

### Deterministic software tests
Unit-test schemas, policy, routing, parsing, idempotency and tool adapters.

### Integration tests
Exercise PostgreSQL/pgvector, Redis, MCP/API contracts and provider adapters.

### AI evaluations
Use versioned datasets for correctness, groundedness, tool selection, citation behavior and refusal/safety behavior.

### Failure and security tests
Inject timeouts, duplicate requests, provider outages, malformed tool output, prompt injection, cross-tenant requests and approval bypass attempts.

## 11. Scaling and Production Topology

Scale agent/API workers separately from retrieval and tool services; split MCP servers by trust domain and move long-running work to durable orchestration.

A typical production topology is:

```text
Global / Regional Load Balancer
            |
     Stateless API replicas
            |
    +-------+--------+
    |                |
AI workers       Policy services
    |                |
Retrieval        Approval/Audit
    |
Java/MCP tool services
    |
Enterprise systems

Managed PostgreSQL / Vector Store
Managed Redis
OpenTelemetry Collector
Secrets / Workload Identity
```

## 12. Key Trade-Off

The supervisor pattern improves governance and debuggability, but can become a coordination bottleneck; use deterministic routing for obvious tasks.

The architecture should be evaluated on a **quality × latency × cost × reliability × security** frontier rather than optimizing model quality alone.

## 13. CI/CD and Deployment Roadmap

```text
Pull Request
   |
lint + unit tests
   |
integration tests
   |
AI/security eval gates
   |
container build + SBOM
   |
staging / shadow traffic
   |
canary
   |
production
   |
SLO + eval monitoring
```

Recommended next production steps:

- Kubernetes/Helm or a managed container platform.
- Workload identity and centralized secrets.
- OpenTelemetry propagation across Python → MCP → Java.
- Schema registry/versioning for tool contracts.
- Per-tenant quotas and cost budgets.
- Durable audit/event retention.
- Load tests and chaos/failure tests.
- Model/prompt/tool-policy canary rollout and rollback.
- Anonymized production-trace sampling into evaluation datasets.


1. Why Python owns AI-heavy orchestration while Java owns enterprise/action-plane concerns.
2. Which decisions must remain deterministic and outside the model.
3. Tenant identity propagation and confused-deputy prevention.
4. Idempotency under retries and ambiguous side-effect failures.
5. Provider/MCP failure modes and graceful degradation.
6. Schema evolution across polyglot services.
7. Human approval and separation-of-duties design.
8. Quality evaluation independent of uptime/latency.
9. Cost controls and token/tool-call budgets.
10. 10×/100× scaling and multi-region/data-residency changes.
11. Observability without leaking confidential prompts.
12. Threat modeling for prompt injection and poisoned tool/RAG content.

## 15. Portfolio Description

> **Enterprise Multi-Agent AI Platform** — Designed and implemented a Python/Java enterprise AI reference platform with explicit control-plane/action-plane boundaries, production-oriented reliability, security/governance, observability, testing and AI evaluation patterns. 

## 16. Production Disclaimer

This is a reference implementation. Before production use, pin and verify SDK/model versions, perform full dependency and container security scans, run end-to-end integration/load/security tests, and integrate the platform with the organization's real identity, secrets, policy, audit, DLP and compliance systems.
