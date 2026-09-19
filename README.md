# Enterprise Multi-Agent AI Platform

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Goals and Non-Goals](#3-goals-and-non-goals)
4. [Architecture Principles](#4-architecture-principles)
5. [System Context — C4 Level 1](#5-system-context--c4-level-1)
6. [Container Architecture — C4 Level 2](#6-container-architecture--c4-level-2)
7. [Agent Architecture](#7-agent-architecture)
8. [Request Lifecycle](#8-request-lifecycle)
9. [Detailed Sequence Diagrams](#9-detailed-sequence-diagrams)
10. [Agent Responsibilities and Contracts](#10-agent-responsibilities-and-contracts)
11. [MCP Tool Plane](#11-mcp-tool-plane)
12. [RAG Architecture](#12-rag-architecture)
13. [Memory Architecture](#13-memory-architecture)
14. [Human-in-the-Loop](#14-human-in-the-loop)
15. [Data Architecture](#15-data-architecture)
16. [API Design](#16-api-design)
17. [Security Architecture](#17-security-architecture)
18. [Threat Model](#18-threat-model)
19. [Reliability and Resilience](#19-reliability-and-resilience)
20. [Failure-Mode Matrix](#20-failure-mode-matrix)
21. [Idempotency and Side-Effect Safety](#21-idempotency-and-side-effect-safety)
22. [Observability](#22-observability)
23. [SLOs and SLIs](#23-slos-and-slis)
24. [Evaluation Architecture](#24-evaluation-architecture)
25. [Testing Strategy](#25-testing-strategy)
26. [Performance and Capacity Planning](#26-performance-and-capacity-planning)
27. [Cost Architecture](#27-cost-architecture)
28. [Deployment Architecture](#28-deployment-architecture)
29. [Kubernetes Production Topology](#29-kubernetes-production-topology)
30. [Multi-Region Design](#30-multi-region-design)
31. [Data Residency and Privacy](#31-data-residency-and-privacy)
32. [CI/CD and Release Engineering](#32-cicd-and-release-engineering)
33. [Model and Prompt Lifecycle](#33-model-and-prompt-lifecycle)
34. [Schema and Tool Versioning](#34-schema-and-tool-versioning)
35. [Architecture Decision Records](#35-architecture-decision-records)
36. [Key Trade-Offs](#36-key-trade-offs)
37. [Production Hardening Roadmap](#37-production-hardening-roadmap)
38. [Principal Engineer Interview Walkthrough](#38-principal-engineer-interview-walkthrough)
39. [Resume Positioning](#39-resume-positioning)
40. [Repository Guide](#40-repository-guide)
41. [Local Development](#41-local-development)
42. [Operational Runbook](#42-operational-runbook)

---

# 1. Executive Summary

Enterprise agent systems are not simply chat applications with more prompts.

A production agent may need to:

- understand an ambiguous business request;
- retrieve private enterprise knowledge;
- delegate specialized reasoning;
- call APIs and tools;
- preserve conversational and task state;
- wait for human approval;
- execute side effects;
- verify whether those side effects succeeded;
- recover from partial failures;
- enforce tenant and identity boundaries;
- expose enough telemetry to debug a non-deterministic workflow;
- evaluate quality before a model or prompt change reaches production.

This repository models those requirements as an **AI control plane** around a set of specialist agents and a separately governed **enterprise action plane**.

The central design rule is:

> **The model may reason about what should happen; deterministic infrastructure decides what is allowed to happen.**

The system therefore separates:

```text
                    PROBABILISTIC
                 AI REASONING PLANE
                         |
             +-----------+-----------+
             |                       |
       Supervisor Agent        Specialist Agents
             |                       |
             +-----------+-----------+
                         |
                    intent / plan
                         |
                         v
                    DETERMINISTIC
                 GOVERNANCE PLANE
                         |
       identity -> policy -> approval -> quotas
                         |
                         v
                    ACTION PLANE
                         |
               Java / Spring MCP
                         |
             enterprise services
```

The platform is designed to be explainable at a **Principal Engineer architecture review**: every trust boundary, state transition, side effect, retry, failure mode, scaling decision, and quality signal has an explicit owner.

---

# 2. Problem Statement

A single general-purpose agent creates several architectural problems.

### 2.1 Context overload

One agent receives business instructions, retrieved documents, tool schemas, conversation history, security rules, intermediate plans, and tool output. The larger the context becomes, the harder it is to control relevance, cost, latency, and prompt-injection exposure.

### 2.2 Excessive privileges

If one agent can search documents, query customers, create tickets, restart services, modify records, and approve actions, compromise of one reasoning loop compromises the whole platform.

### 2.3 Weak observability

A final response does not explain:

- which evidence was retrieved;
- why a tool was chosen;
- what arguments were sent;
- whether an approval was requested;
- whether the side effect committed;
- which agent produced a bad decision.

### 2.4 Failure ambiguity

An HTTP timeout after a mutation does **not** imply that the mutation failed.

```text
Agent ---- request ----> Tool
Agent <---- timeout ---- Tool

Question:
Did the tool fail before committing,
or commit successfully and lose the response?
```

Blind retrying can duplicate side effects.

### 2.5 Model changes become platform changes

Without stable contracts, changing a model can unexpectedly change tool selection, JSON shape, latency, cost, or refusal behavior.

The platform solves these problems through specialization, stable contracts, deterministic enforcement, evidence capture, and explicit operational semantics.

---

# 3. Goals and Non-Goals

## Goals

1. Support multiple specialized enterprise agents.
2. Give the supervisor a small, understandable delegation surface.
3. Keep privileged actions behind narrow MCP tools.
4. Support tenant-scoped enterprise knowledge retrieval.
5. Maintain conversation/task memory without making memory authoritative.
6. Require human approval for selected high-risk actions.
7. Produce end-to-end traces across agent and tool boundaries.
8. Make quality measurable through offline evaluation.
9. Scale AI workloads independently from enterprise services.
10. Support model/provider migration without changing application APIs.

## Non-Goals

This reference implementation is not intended to:

- replace an enterprise IAM platform;
- act as a complete DLP product;
- provide unrestricted autonomous shell access;
- allow the LLM to decide its own permissions;
- use long-term memory as a source of truth;
- auto-approve destructive actions;
- guarantee correctness solely because several agents agree;
- treat a model judge as an authoritative security control.

---

# 4. Architecture Principles

## 4.1 Model reasoning is advisory

LLM output is data.

Plans, classifications, tool arguments, summaries, and recommendations must be validated before they cross a trust boundary.

## 4.2 Least privilege by agent

Each specialist receives only the tools and context required for its job.

```text
Research Agent
  -> knowledge search
  -> document retrieval
  X  no mutation tools

Execution Agent
  -> approved enterprise tools
  X  no unrestricted DB access

Review Agent
  -> evidence + proposed answer
  X  no production mutation tools
```

## 4.3 Separate reads from writes

Read operations can often be retried.

Writes require:

- authorization;
- idempotency;
- approval when appropriate;
- audit;
- verification.

## 4.4 Evidence before confidence

A confident answer without evidence is not more trustworthy.

The platform prefers:

```text
claim
  -> evidence id
  -> source
  -> retrieval/tool event
  -> trace
```

## 4.5 Stable enterprise contracts

Applications should depend on enterprise capabilities such as:

```text
customer.lookup
ticket.create
deployment.inspect
```

rather than provider-specific model or backend implementation details.

## 4.6 Bounded autonomy

Every run should have budgets:

- maximum turns;
- maximum tool calls;
- maximum elapsed time;
- maximum tokens;
- maximum estimated cost;
- maximum repair/retry cycles.

---

# 5. System Context — C4 Level 1

```text
+-------------------+
| Enterprise User   |
| Web / API / App   |
+---------+---------+
          |
          | request
          v
+------------------------------------------------+
|        Enterprise Multi-Agent Platform         |
|                                                |
|  Understand -> Retrieve -> Reason -> Act       |
|  -> Verify -> Respond                          |
+----+------------------+-------------------+----+
     |                  |                   |
     v                  v                   v
+---------+       +------------+       +-----------+
| Identity|       | Knowledge  |       | Enterprise|
| Provider|       | Systems    |       | Systems   |
| OIDC    |       | Docs / KB  |       | CRM / Ops |
+---------+       +------------+       +-----------+
                         |
                         v
                  +--------------+
                  | Observability|
                  | / Audit / SIEM|
                  +--------------+
```

### Actors

| Actor | Responsibility |
|---|---|
| Enterprise user | Requests information or actions |
| Calling application | Presents UI/API and identity token |
| Identity provider | Authenticates users/services |
| Multi-agent platform | Coordinates reasoning and governed actions |
| Knowledge systems | Provide tenant-scoped enterprise evidence |
| Enterprise systems | Perform business/operational actions |
| Human approver | Authorizes selected high-risk actions |
| Observability/SIEM | Receives operational/security evidence |

---

# 6. Container Architecture — C4 Level 2

```text
                              +------------------+
                              | Client / UI      |
                              +--------+---------+
                                       |
                                       v
+-----------------------------------------------------------------------+
|                         AI CONTROL PLANE                              |
|                                                                       |
| +-------------------+       +---------------------------------------+ |
| | FastAPI Gateway   |------>| OpenAI Agents Runtime                 | |
| | auth / validation |       | Supervisor + Specialists             | |
| +---------+---------+       +------+----------+-----------+--------+ |
|           |                        |          |           |          |
|           |                        v          v           v          |
|           |                     Research   Reasoning    Review       |
|           |                        |                                  |
|           |                        v                                  |
|           |                 RAG / pgvector                            |
|           |                                                           |
|           +----------------------> Execution Agent                     |
|                                      |                                |
+--------------------------------------|--------------------------------+
                                       |
                                       | MCP Streamable HTTP
                                       v
+-----------------------------------------------------------------------+
|                         ACTION PLANE                                  |
|                                                                       |
| +---------------------------------------------------------------+     |
| | Java / Spring AI MCP Server                                  |     |
| | tool schemas | validation | domain adapters | action policy   |     |
| +------------+----------------------+---------------------------+     |
|              |                      |                                 |
+--------------|----------------------|---------------------------------+
               |                      |
               v                      v
          CRM / Tickets          Ops / Internal APIs

+--------------------+     +-------------------+     +------------------+
| PostgreSQL         |     | Redis             |     | OTel/Prometheus  |
| state + pgvector   |     | cache/ephemeral   |     | traces/metrics   |
+--------------------+     +-------------------+     +------------------+
```

### Why two languages?

Python is used where the ecosystem is strongest for:

- agent orchestration;
- model interaction;
- RAG experimentation;
- evaluation;
- AI-specific libraries.

Java is used to demonstrate:

- strongly typed enterprise service boundaries;
- Spring Boot integration;
- Spring AI MCP;
- mature enterprise operational patterns;
- independently deployable action services.

This is not “polyglot for novelty.” It demonstrates a realistic organization in which the AI platform and enterprise service estate evolve independently.

---

# 7. Agent Architecture

```text
                         +-------------------+
                         | Supervisor Agent  |
                         +----+---+---+------+
                              |   |   |
               +--------------+   |   +---------------+
               |                  |                   |
               v                  v                   v
       +---------------+  +---------------+   +---------------+
       | Research      |  | Reasoning     |   | Execution     |
       | Agent         |  | Agent         |   | Agent         |
       +-------+-------+  +-------+-------+   +-------+-------+
               |                  |                   |
               v                  |                   v
         Knowledge/RAG            |               MCP Tools
                                  |
                                  v
                           structured plan
                                  |
                                  v
                         +----------------+
                         | Review Agent   |
                         +--------+-------+
                                  |
                                  v
                           final response
```

## Why specialist agents?

Specialization provides four controls.

### Context isolation

The Research Agent does not need mutation tools.

### Permission isolation

The Execution Agent does not need every knowledge source.

### Evaluation isolation

Research quality can be measured separately from execution quality.

### Model specialization

A future platform may use:

- inexpensive model for routing;
- retrieval-focused model for query rewriting;
- stronger reasoning model for complex planning;
- low-latency model for review.

---

# 8. Request Lifecycle

A typical request progresses through the following states.

```text
RECEIVED
   |
   v
VALIDATED
   |
   v
CONTEXT_BUILT
   |
   v
PLANNED
   |
   +-------- read-only --------+
   |                           |
   v                           v
RETRIEVING                  REVIEWING
   |                           |
   v                           |
EVIDENCE_READY                 |
   |                           |
   +------------+--------------+
                |
                v
         ACTION_REQUIRED?
           /         \
         no           yes
         |             |
         |             v
         |        POLICY_CHECK
         |          /      \
         |       deny     allow
         |        |          |
         |        |       approval?
         |        |       /      \
         |        |     yes       no
         |        |      |         |
         |        |   WAITING      |
         |        |      |         |
         |        |   APPROVED     |
         |        |      |         |
         |        +------|---------+
         |               v
         |            EXECUTING
         |               |
         |            VERIFYING
         |               |
         +---------------+
                |
                v
             REVIEW
                |
                v
            COMPLETED
```

The state machine matters because a user-facing request can outlive a single HTTP connection once approval or long-running actions are introduced.

---

# 9. Detailed Sequence Diagrams

## 9.1 Knowledge question

```text
User        API       Supervisor      Research       Vector DB      Review
 |           |            |              |               |            |
 |--ask----->|            |              |               |            |
 |           |--run------>|              |               |            |
 |           |            |--delegate--->|               |            |
 |           |            |              |--search------>|            |
 |           |            |              |<--evidence----|            |
 |           |            |<--answer-----|               |            |
 |           |            |----------------------------->|            |
 |           |            |<-----------------------------|            |
 |           |<--final----|                                           |
 |<--reply---|                                                        |
```

## 9.2 Governed action

```text
User      API    Supervisor   Execution   Policy   MCP/Java   System
 |         |         |            |         |         |         |
 |--task-->|         |            |         |         |         |
 |         |--run--->|            |         |         |         |
 |         |         |--delegate->|         |         |         |
 |         |         |            |--check->|         |         |
 |         |         |            |<--allow-|         |         |
 |         |         |            |--------tool------>|         |
 |         |         |            |         |         |--call-->|
 |         |         |            |         |         |<--ok----|
 |         |         |            |<-------result-----|         |
 |         |         |<--verified-|                   |         |
 |         |<--final-|                                |         |
 |<--reply-|                                           |         |
```

## 9.3 Action requiring approval

```text
Execution Agent
      |
      v
Policy Engine
      |
      +---- REQUIRE_APPROVAL
      |
      v
Approval Record
      |
      v
WAITING_FOR_HUMAN
      |
 Human approves
      |
      v
Validate:
 - same tenant?
 - same action?
 - same normalized args?
 - unexpired?
 - unused?
      |
      v
Execute Tool
      |
      v
Consume Approval
      |
      v
Verify Result
```

---

# 10. Agent Responsibilities and Contracts

## Supervisor Agent

### Responsibilities

- classify request;
- decide whether research/reasoning/execution is required;
- delegate;
- keep the workflow bounded;
- assemble final result.

### Must not

- directly mutate enterprise systems;
- fabricate tool success;
- bypass approval;
- treat memory as authoritative enterprise truth.

## Research Agent

Input:

```json
{
  "question": "What is the refund approval policy?",
  "tenant_id": "acme"
}
```

Output concept:

```json
{
  "summary": "Manager approval is required above the threshold.",
  "evidence": [
    {
      "source": "refund-policy.pdf",
      "chunk": 12,
      "claim": "Refunds above $500 require manager approval."
    }
  ]
}
```

## Reasoning Agent

Produces a structured plan, not a side effect.

```json
{
  "goal": "Resolve customer refund request",
  "steps": [
    "retrieve policy",
    "inspect customer",
    "determine whether approval is required"
  ],
  "requires_action": true
}
```

## Execution Agent

Execution is constrained by the available MCP tool schemas.

It must never receive:

- raw production database credentials;
- arbitrary shell access;
- broad cloud-admin credentials;
- approval authority.

## Review Agent

Checks:

- answer addresses request;
- enterprise claims have evidence;
- action result is not overstated;
- unsupported claims are removed;
- response is suitable for the caller.

A reviewer is **not** a substitute for deterministic policy.

---

# 11. MCP Tool Plane

MCP is used as the typed boundary between the agent runtime and enterprise capabilities.

```text
Agent Runtime
     |
     | list_tools
     v
MCP Gateway / Server
     |
     | tool schema
     v
Agent selects permitted tool
     |
     | call_tool(arguments)
     v
Validation / Policy / Domain Adapter
     |
     v
Enterprise System
```

## Tool design rules

Good:

```text
create_support_ticket(
    customer_id,
    subject,
    priority,
    idempotency_key
)
```

Bad:

```text
execute_sql(query)
run_shell(command)
call_any_url(url, body)
```

The first exposes a business capability.

The second exposes infrastructure power.

## Tool metadata

Every enterprise tool should define:

- stable name;
- description;
- input JSON schema;
- output schema;
- read/write classification;
- risk class;
- required scope;
- idempotency behavior;
- timeout;
- retry policy;
- audit policy;
- approval policy.

Example registry record:

```yaml
tool: ticket.create
version: v2
risk: medium
mutation: true
scope: support.ticket.write
idempotent: true
approval: false
timeout_ms: 3000
owner: customer-platform
```

---

# 12. RAG Architecture

```text
                   INGESTION
Document
   |
parse / normalize
   |
chunk
   |
metadata enrichment
   |
embedding
   |
PostgreSQL + pgvector
   |
tenant / ACL metadata


                   SERVING
Question
   |
query rewrite
   |
vector retrieval
   |
metadata / tenant filter
   |
top-K evidence
   |
optional reranking
   |
Research Agent
   |
grounded answer
```

## Chunk metadata

Recommended metadata:

```json
{
  "tenant_id": "acme",
  "document_id": "policy-2026-04",
  "version": "7",
  "chunk_id": "policy-2026-04:17",
  "title": "Refund Policy",
  "section": "Manager Approval",
  "classification": "internal",
  "effective_from": "2026-04-01",
  "effective_to": null
}
```

## Why metadata matters

Embedding similarity alone cannot enforce:

- tenant boundaries;
- document ACLs;
- effective dates;
- regulatory region;
- document version;
- retention policy.

These are deterministic filters.

## Retrieval quality metrics

Track separately:

```text
Recall@K
MRR
nDCG@K
context precision
context relevance
answer correctness
groundedness
citation precision
citation recall
```

A good final answer can hide poor retrieval on an easy dataset. Measure both.

---

# 13. Memory Architecture

Memory has several distinct meanings.

```text
Conversation memory
  short-lived dialogue context

Task memory
  state for one multi-step job

User preference memory
  durable preferences, tightly governed

Enterprise knowledge
  authoritative documents/data

Audit history
  immutable operational evidence
```

These must not be collapsed into one vector store.

## Memory precedence

```text
authoritative enterprise system
        >
approved enterprise knowledge
        >
current task state
        >
conversation history
        >
inferred preference
```

Conversation memory must never override authoritative business state.

---

# 14. Human-in-the-Loop

Human approval is a security and governance state transition, not a sentence in a prompt.

## Approval object

```json
{
  "approval_id": "apr_123",
  "tenant_id": "acme",
  "requester": "user_42",
  "approver": "manager_7",
  "tool": "deployment.rollback",
  "argument_digest": "sha256:...",
  "expires_at": "2026-09-19T14:00:00Z",
  "status": "APPROVED",
  "used_at": null
}
```

## Approval invariants

An approval should be:

- bound to a tenant;
- bound to a specific tool;
- bound to normalized arguments;
- expiring;
- one-use;
- auditable;
- optionally subject to separation of duties.

Bad:

```text
"approved=true"
```

Good:

```text
approval token
 -> hashed at rest
 -> lookup
 -> exact action digest match
 -> TTL valid
 -> approver authorized
 -> atomically consumed
```

---

# 15. Data Architecture

## Logical entities

```text
Tenant
Principal
Conversation
Message
Task
AgentRun
Evidence
ToolInvocation
Approval
AuditEvent
EvaluationRun
PromptVersion
ModelAlias
```

## Suggested relational model

```text
tenants
  id PK

conversations
  id PK
  tenant_id FK
  created_at

messages
  id PK
  conversation_id FK
  role
  content
  created_at

knowledge_chunks
  id PK
  tenant_id
  document_id
  content
  embedding vector
  metadata jsonb

agent_runs
  id PK
  tenant_id
  workflow_name
  model_alias
  status
  started_at
  completed_at

tool_invocations
  id PK
  run_id
  tool_name
  arguments_digest
  status
  latency_ms
  idempotency_key

approvals
  id PK
  tenant_id
  tool_name
  argument_digest
  requester
  approver
  status
  expires_at

audit_events
  id PK
  tenant_id
  event_type
  event_hash
  previous_hash
  created_at
```

## PostgreSQL vs Redis

Use PostgreSQL for durable truth.

Use Redis for:

- ephemeral rate counters;
- short-lived caches;
- distributed locks;
- temporary approval/session state only if loss is acceptable or reconstructed.

Do not make Redis the only durable record of a critical approval.

---

# 16. API Design

## Stable external API

Example:

```http
POST /v1/chat
Authorization: Bearer <token>
Idempotency-Key: <uuid>
X-Tenant-Id: acme
```

Request:

```json
{
  "session_id": "sess_123",
  "message": "Find the refund policy and create a ticket if manager approval is needed."
}
```

Response:

```json
{
  "request_id": "req_456",
  "session_id": "sess_123",
  "status": "completed",
  "answer": "Manager approval is required. A support ticket was created.",
  "citations": [
    {
      "source": "refund-policy.pdf",
      "chunk_id": "refund-policy:12"
    }
  ],
  "actions": [
    {
      "tool": "ticket.create",
      "status": "succeeded",
      "reference": "T-18291"
    }
  ]
}
```

## Async operation

Long-lived jobs should return:

```http
202 Accepted
```

```json
{
  "task_id": "task_789",
  "status": "waiting_for_approval"
}
```

Clients can poll, subscribe to events, or receive a callback.

---

# 17. Security Architecture

```text
                         ZERO-TRUST FLOW

User Token
   |
JWT validation
   |
Principal + tenant
   |
Request policy
   |
Agent
   |
Dynamic tool exposure
   |
Tool input validation
   |
Authorization
   |
Approval if needed
   |
Workload identity
   |
MCP server
   |
Domain authorization
   |
Enterprise system
```

## Security controls

### Identity

Production:

- OIDC/OAuth 2.x;
- workload identity;
- short-lived credentials;
- issuer/audience/expiry validation.

### Authorization

Evaluate:

```text
principal
tenant
role/scope
tool
action
resource
environment
risk
```

### Prompt injection

Assume untrusted instructions may arrive from:

- user prompt;
- document;
- webpage;
- ticket;
- email;
- tool output;
- image text;
- metadata.

Never allow retrieved text to redefine system policy.

### Secret handling

Secrets must remain outside:

- prompts;
- conversation memory;
- tool descriptions;
- tool arguments when avoidable;
- logs;
- traces.

### Egress

Tool services should have explicit outbound allowlists.

This limits SSRF and data exfiltration.

---

# 18. Threat Model

| Threat | Example | Primary Control |
|---|---|---|
| Direct prompt injection | “Ignore policy and…” | guardrails + deterministic policy |
| Indirect injection | malicious text in document | untrusted-content boundary |
| Cross-tenant retrieval | tenant A sees tenant B docs | DB filter/RLS |
| Confused deputy | low privilege user causes privileged tool call | propagate end-user identity |
| Tool poisoning | malicious MCP server/schema | trusted registry/schema pinning |
| Secret exfiltration | model sends token to tool | DLP + narrow tools |
| SSRF | tool fetches attacker URL | egress allowlist |
| Replay | same approval reused | one-use token |
| Duplicate mutation | retry creates two tickets | idempotency key |
| Runaway agent | infinite tool loop | turn/tool/cost budgets |
| Audit tampering | operator edits logs | immutable export/hash chain |
| Model drift | new model selects risky tools | eval/canary gates |

---

# 19. Reliability and Resilience

## Timeout hierarchy

A request needs a deadline budget.

Example:

```text
End-to-end deadline       20 s
  supervisor              3 s
  retrieval               1 s
  reasoning               5 s
  tool call               4 s
  review                  3 s
  reserve                 4 s
```

Do not give every downstream dependency the full 20-second timeout.

## Retry rules

Safe candidates:

- read-only retrieval;
- model call before side effects;
- idempotent tool with stable idempotency key.

Unsafe blind retry:

- payment;
- email send;
- deployment mutation;
- record creation without idempotency.

## Circuit breaker

```text
CLOSED
  |
failures exceed threshold
  v
OPEN
  |
cooldown
  v
HALF_OPEN
  |
success -> CLOSED
failure -> OPEN
```

Circuit breakers prevent retry storms against a failing provider.

---

# 20. Failure-Mode Matrix

| Failure | Detection | User impact | Recovery |
|---|---|---|---|
| Model timeout | deadline exceeded | delayed/failed answer | bounded retry/fallback |
| Vector DB unavailable | DB error | no enterprise grounding | fail closed for authoritative query |
| Redis unavailable | health/exception | cache/rate degradation | DB/local fallback where safe |
| MCP server unavailable | tool connection error | action unavailable | retry/fallback/manual path |
| Tool returns invalid schema | validation error | action not trusted | reject + alert |
| Mutation response lost | timeout after send | ambiguous outcome | query by idempotency key |
| Approval expires | TTL | action paused | request new approval |
| Review agent fails | model error | no review | deterministic fallback or fail |
| Provider rate limit | 429 | latency | backoff/alternate provider |
| Prompt injection detected | guardrail | request blocked | safe response/audit |
| Cross-tenant request | authorization | denied | security audit |
| Runaway loop | budget exceeded | partial task | terminate safely |

---

# 21. Idempotency and Side-Effect Safety

Every mutation should accept an idempotency key.

```text
request_id + logical_step
        |
        v
idempotency_key
        |
        v
Tool Service
   |
   +-- unseen -> execute + persist result
   |
   +-- seen   -> return stored result
```

Example:

```json
{
  "tool": "ticket.create",
  "arguments": {
    "customer_id": "C123",
    "subject": "Refund approval",
    "idempotency_key": "task-77:ticket-create:1"
  }
}
```

This converts many ambiguous retries into safe retries.

---

# 22. Observability

The platform needs both conventional distributed tracing and AI-specific spans.

## Trace hierarchy

```text
request
 |
 +-- auth
 +-- supervisor agent
 |    +-- model generation
 |    +-- handoff/research
 |    |    +-- embedding
 |    |    +-- vector query
 |    +-- execution
 |         +-- MCP call
 |              +-- Java service
 |                   +-- enterprise API
 +-- review agent
 +-- persistence
```

## Required trace attributes

```text
request.id
tenant.id
principal.id (pseudonymous if required)
workflow.name
agent.name
model.alias
provider.model
prompt.version
tool.name
tool.version
approval.required
retrieval.top_k
tokens.input
tokens.output
cost.estimated
```

## Metrics

### Platform

- requests/sec;
- error rate;
- p50/p95/p99 latency;
- active runs;
- queue depth.

### Model

- model latency;
- token usage;
- rate-limit errors;
- fallback rate;
- cost.

### Agent

- turns/run;
- tool calls/run;
- handoffs/run;
- budget-exceeded rate.

### Retrieval

- query latency;
- candidates;
- reranker latency;
- empty-retrieval rate.

### Tools

- tool latency;
- tool error rate;
- approval rate;
- idempotency replay rate.

---

# 23. SLOs and SLIs

Example service objectives:

| SLI | Target |
|---|---|
| API availability | 99.9% monthly |
| Read-only p95 | < 8 s |
| Tool execution p95 excluding approval | < 12 s |
| Cross-tenant leakage | 0 tolerated |
| Unauthorized mutation | 0 tolerated |
| Tool result schema validity | > 99.99% |
| Trace correlation coverage | > 99% |
| Evaluation regression escape | tracked as quality incident |

Error budgets should influence release velocity.

A model quality regression can be an operational incident even when HTTP availability remains 100%.

---

# 24. Evaluation Architecture

```text
Golden Dataset
      |
      +-------------------+
      |                   |
  Candidate           Baseline
      |                   |
      +---------+---------+
                |
          captured runs
                |
   +------------+-------------+
   |            |             |
deterministic  semantic      agent
graders        judge         trajectory
   |            |             |
   +------------+-------------+
                |
         regression gate
```

## Evaluation dimensions

### Supervisor

- correct delegation;
- unnecessary delegation;
- task completion.

### Research

- Recall@K;
- evidence relevance;
- citation correctness.

### Reasoning

- plan completeness;
- constraint adherence.

### Execution

- correct tool;
- correct arguments;
- unnecessary tool rate;
- policy compliance.

### Review

- unsupported-claim detection;
- correction precision.

### End-to-end

- task success;
- groundedness;
- latency;
- cost;
- safety.

## Judge calibration

LLM judges should be calibrated against human labels.

Track:

- agreement;
- confusion matrix;
- order bias;
- verbosity bias;
- judge-model drift.

---

# 25. Testing Strategy

## Unit tests

Test:

- schemas;
- policy;
- chunking;
- routing;
- tool argument normalization;
- idempotency;
- approval digest.

## Contract tests

Python and Java must agree on:

- tool names;
- JSON schema;
- required fields;
- error format;
- version behavior.

## Integration tests

Use real local:

- PostgreSQL/pgvector;
- Redis;
- MCP server.

Mock external enterprise systems.

## End-to-end tests

```text
request
 -> supervisor
 -> retrieval
 -> tool
 -> review
 -> persisted result
```

## Adversarial tests

Include:

- prompt injection;
- malicious retrieved document;
- secret in tool argument;
- cross-tenant resource id;
- duplicate mutation;
- expired approval;
- tool schema mismatch;
- provider timeout;
- tool output containing instructions.

---

# 26. Performance and Capacity Planning

Assume:

```text
100 requests/s
2.5 average model calls/request
0.8 retrieval queries/request
0.4 tool calls/request
```

Then:

```text
model calls      = 250/s
retrieval QPS    = 80/s
tool QPS         = 40/s
```

If average model latency is 2 seconds:

```text
approximate concurrent model calls
= 250 * 2
= 500
```

This is why agent servers should be asynchronous and model-provider concurrency must be explicitly controlled.

## Little's Law

```text
L = λW
```

Where:

- `L` = average concurrent work;
- `λ` = arrival rate;
- `W` = average time in system.

For 100 requests/s and 6-second average latency:

```text
L = 100 * 6 = 600 concurrent requests
```

Capacity planning must account for tail latency, not only averages.

---

# 27. Cost Architecture

Per-request estimated cost:

```text
C_request =
  C_supervisor
+ C_research
+ C_reasoning
+ C_review
+ C_embeddings
+ C_reranking
+ C_tools
+ C_infrastructure
```

## Cost controls

- route simple requests to cheaper models;
- skip Research Agent when no enterprise knowledge is needed;
- cache embeddings;
- cap retrieved context;
- summarize old conversation history;
- cap turns and tool calls;
- use deterministic validators before expensive model judges;
- avoid invoking review when a deterministic result is sufficient.

## Budget object

```json
{
  "max_turns": 8,
  "max_tool_calls": 6,
  "max_input_tokens": 30000,
  "max_output_tokens": 5000,
  "max_elapsed_ms": 20000,
  "max_estimated_cost_usd": 0.50
}
```

---

# 28. Deployment Architecture

```text
Internet / Enterprise Network
            |
          WAF
            |
      API Gateway
            |
   Kubernetes Ingress
            |
 +----------+----------+
 |                     |
Python Agent API   Java MCP Service
 |                     |
 |                workload identity
 |                     |
 +----------+----------+
            |
   Managed PostgreSQL
            |
        pgvector

Redis Cluster
OTel Collector
Prometheus/Grafana
Secrets Manager
SIEM / Audit Sink
```

The database and Redis should normally be managed services in production rather than containers inside the application cluster.

---

# 29. Kubernetes Production Topology

Recommended workloads:

```text
Deployment: agent-api
Deployment: agent-workers
Deployment: java-mcp-read
Deployment: java-mcp-write
Deployment: ingestion-workers
Deployment: eval-workers

HPA:
  CPU
  request concurrency
  queue depth

PDB:
  protect critical serving replicas

NetworkPolicy:
  agent-api -> approved MCP only
  MCP -> approved enterprise endpoints only
```

Separate read-only and mutation MCP services when the trust difference is significant.

---

# 30. Multi-Region Design

```text
             Global Router
              /        \
             /          \
        Region A      Region B
        Agent API     Agent API
        MCP tools     MCP tools
        RAG replica   RAG replica
             \          /
              \        /
          Global config plane
```

## Region-local

Keep region-local when possible:

- prompts containing regulated data;
- vector indexes;
- conversation state;
- tool execution;
- audit payloads.

## Globally distributed

Distribute:

- model aliases;
- prompt version ids;
- policy bundles;
- tool registry metadata;
- feature flags.

Avoid globally replicating raw confidential prompts merely for convenience.

---

# 31. Data Residency and Privacy

Classify data before sending it to any model.

Example classes:

```text
PUBLIC
INTERNAL
CONFIDENTIAL
RESTRICTED
```

Routing can enforce:

```text
RESTRICTED
 -> approved region
 -> approved provider
 -> no trace content
 -> no persistent model storage
```

Retention must be explicit for:

- conversation messages;
- traces;
- retrieved chunks;
- tool arguments/results;
- approvals;
- audit logs.

---

# 32. CI/CD and Release Engineering

```text
Pull Request
   |
format / lint
   |
unit tests
   |
contract tests
   |
integration tests
   |
AI eval suite
   |
security tests
   |
build containers
   |
SBOM + image scan
   |
staging
   |
shadow / canary
   |
production
```

## Deployment gates

A release should fail if:

- deterministic tests fail;
- cross-tenant security test fails;
- tool schema compatibility breaks;
- critical eval metric regresses beyond threshold;
- container has disallowed critical vulnerability;
- migration is incompatible.

---

# 33. Model and Prompt Lifecycle

Do not hard-code “the model” as business logic.

Use aliases:

```text
enterprise-fast
enterprise-reasoning
enterprise-review
```

Mapping:

```yaml
enterprise-fast:
  provider: provider-a
  model: model-x
  config_version: 17
```

## Migration

```text
new model
 -> offline eval
 -> shadow
 -> 1% canary
 -> compare quality/latency/cost
 -> 10%
 -> 50%
 -> 100%
```

Rollback changes the alias, not every application.

## Prompt versioning

Every trace should include:

```text
prompt.id
prompt.version
model.alias
policy.version
tool.schema.version
```

Otherwise a bad production run cannot be reproduced.

---

# 34. Schema and Tool Versioning

Tool schemas are APIs.

Breaking changes need the same discipline as REST/gRPC.

## Compatible

Adding an optional response field.

## Potentially breaking

Changing:

```text
priority: "high"
```

to:

```text
priority: 3
```

## Version strategy

Prefer:

```text
ticket.create.v1
ticket.create.v2
```

during migration rather than silently changing semantics underneath the model.

---

# 35. Architecture Decision Records

## ADR-001 — Supervisor pattern

**Decision:** use a supervisor with specialists.

**Reason:** centralizes workflow control, simplifies permissions and tracing.

**Rejected:** unrestricted peer-to-peer agents.

**Trade-off:** supervisor can become a latency/coordination bottleneck.

## ADR-002 — MCP for action boundary

**Decision:** expose enterprise capabilities through typed MCP tools.

**Reason:** standard tool discovery/calling and language-independent boundary.

**Rejected:** model directly calling arbitrary internal APIs.

## ADR-003 — Java action plane

**Decision:** keep enterprise action services independently deployable in Java/Spring.

**Reason:** typed domain boundary, enterprise integration ecosystem, polyglot organizational realism.

## ADR-004 — PostgreSQL + pgvector

**Decision:** begin with relational state and vectors in PostgreSQL.

**Reason:** operational simplicity and transactional metadata.

**Revisit when:** vector corpus/latency/recall requirements justify a specialized vector system.

## ADR-005 — Deterministic approval

**Decision:** approval is enforced outside the model.

**Reason:** an LLM cannot be its own authorization authority.

---

# 36. Key Trade-Offs

## Multi-agent vs single-agent

Multi-agent:

+ specialization;
+ permission isolation;
+ easier per-stage evaluation.

- more model calls;
- higher latency;
- orchestration complexity.

## MCP gateway vs direct tools

Gateway:

+ centralized governance;
+ stable tool surface;
+ credential isolation.

- extra network hop;
- critical dependency.

## pgvector vs dedicated vector DB

pgvector:

+ operational simplicity;
+ joins with metadata;
+ transactions.

- specialized systems may scale/search better for very large workloads.

## synchronous vs durable workflow

Synchronous:

+ simple;
+ low operational overhead.

Durable:

+ survives approval delays/restarts;
+ explicit state machine.

For production workflows that can pause for minutes/hours, durable orchestration is usually preferable.

---

# 37. Production Hardening Roadmap

## Phase 1 — Reference platform

- FastAPI gateway;
- specialist agents;
- pgvector;
- Java MCP;
- Docker Compose.

## Phase 2 — Enterprise identity

- OIDC;
- workload identity;
- tenant authorization;
- secret manager.

## Phase 3 — Reliable actions

- idempotency;
- durable approvals;
- outbox/inbox;
- distributed locks;
- compensation.

## Phase 4 — Observability

- full OTel propagation;
- dashboards;
- SLOs;
- audit export.

## Phase 5 — AI governance

- prompt registry;
- model aliases;
- eval gates;
- canaries;
- cost budgets.

## Phase 6 — Scale

- Kubernetes;
- regional deployment;
- queue-backed workers;
- dedicated ingestion;
- capacity/load tests.

---

---

# 39. Portfolio Positioning

### Short version

**Enterprise Multi-Agent AI Platform** — Designed a Python/Java agent platform using supervised specialist agents, tenant-scoped RAG, MCP enterprise tools, memory, HITL approval, observability and evaluation controls.


# 40. Repository Guide

The repository is organized around two major runtime boundaries.

```text
enterprise-multi-agent-ai-platform/
|
+-- python-ai/
|   +-- app/
|   |   +-- agents.py
|   |   +-- config.py
|   |   +-- database.py
|   |   +-- main.py
|   |   +-- memory.py
|   |   +-- models.py
|   |   +-- rag.py
|   |   `-- schemas.py
|   +-- tests/
|   +-- Dockerfile
|   `-- requirements.txt
|
+-- java-tools/
|   +-- src/main/
|   +-- src/test/
|   +-- Dockerfile
|   `-- pom.xml
|
+-- evals/
+-- infra/
+-- docs/
+-- docker-compose.yml
+-- Makefile
`-- README.md
```

### Python service

Owns:

- agent orchestration;
- RAG;
- memory;
- API;
- model runtime.

### Java service

Owns:

- enterprise MCP tools;
- typed domain integration;
- independently deployable action boundary.

### Infrastructure

Owns local:

- PostgreSQL/pgvector;
- Redis;
- monitoring configuration.

---

# 41. Local Development

## Prerequisites

Recommended:

- Docker + Docker Compose;
- Python 3.12 if running outside containers;
- Java 21;
- Maven;
- model-provider API credentials.

## Configure

```bash
cp .env.example .env
```

Add credentials to `.env`.

Do not commit `.env`.

## Start

```bash
docker compose up --build
```

## Test Python

```bash
make python-test
```

or:

```bash
cd python-ai
pytest -q
```

## Test Java

```bash
make java-test
```

or:

```bash
cd java-tools
mvn test
```

## Shut down

```bash
docker compose down -v
```

---

# 42. Operational Runbook

## Symptom: model requests are timing out

Check:

1. provider latency/rate limits;
2. request deadline;
3. concurrent model calls;
4. retry amplification;
5. oversized context.

Mitigation:

- shed load;
- route to fallback;
- reduce context;
- disable nonessential review;
- increase capacity only after confirming bottleneck.

## Symptom: retrieval returns no evidence

Check:

- tenant filter;
- ingestion completion;
- embedding model/version;
- vector index;
- query rewrite.

For authoritative enterprise questions, prefer an explicit “insufficient evidence” response over an ungrounded answer.

## Symptom: MCP tool unavailable

Check:

- Java service health;
- MCP connection;
- tool discovery;
- network policy;
- service identity.

Do not silently claim the action succeeded.

## Symptom: duplicate business actions

Check:

- idempotency key propagation;
- retry logs;
- timeout after commit;
- downstream idempotency store.

## Symptom: cost spike

Check:

- turns/run;
- tool calls/run;
- input context size;
- retrieval top-K;
- repeated retries;
- model alias rollout.

## Symptom: quality regression after model change

Rollback the model alias, preserve traces, run candidate vs baseline evaluation, and inspect regressions by stage rather than only aggregate score.

---

# Final Architecture Summary

The essential architecture can be reduced to six rules:

```text
1. SPECIALIZE
   Supervisor + narrowly scoped agents.

2. GROUND
   Enterprise claims come from tenant-scoped evidence.

3. GOVERN
   Deterministic identity, authorization and approval.

4. CONTAIN
   Narrow MCP tools instead of broad infrastructure access.

5. VERIFY
   Tool results and model outputs are evidence, not assumptions.

6. MEASURE
   Trace quality, reliability, latency, cost and security independently.
```

That is the difference between an impressive multi-agent demo and an enterprise AI platform that can survive an architecture review.
