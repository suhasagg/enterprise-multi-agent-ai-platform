# Architecture decisions

## AI plane vs action plane
The Python service owns reasoning/orchestration. The Java service owns enterprise side effects. MCP is the protocol boundary.

## Multi-agent topology
A supervisor can invoke specialist agents as tools. This avoids unrestricted peer-to-peer chatter and gives one place to enforce policy.

## RAG
Tenant-scoped embeddings are stored in pgvector. Production deployments can replace this with Azure AI Search without changing the agent contract.

## Memory
Conversation messages are durable in PostgreSQL. The prompt only receives a bounded recent window to prevent unbounded context growth.

## Safety
- tenant identifier propagated to MCP
- execution agent is separate from research/reasoning
- risk assessment tool exists before sensitive actions
- no direct DB credentials are exposed to the model
- reviewer checks final output
- production should enforce approval outside the model, not merely in instructions

## Reliability
Production additions should include workflow checkpoints, idempotency keys, circuit breakers, tool timeouts, retries with budgets, and dead-letter handling.
