import json
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from agents import Agent, Runner, function_tool
from agents.mcp import MCPServerStreamableHttp
from .config import settings
from .rag import search

@dataclass
class RunContext:
    tenant_id: str
    db: AsyncSession

def build_agents(ctx: RunContext, mcp_server: MCPServerStreamableHttp):
    @function_tool
    async def search_enterprise_knowledge(query: str) -> str:
        """Search tenant-scoped enterprise knowledge. Use before making claims about internal policy."""
        hits = await search(ctx.db, ctx.tenant_id, query)
        return json.dumps(hits)

    research = Agent(
        name="Research Agent",
        model=settings.openai_model,
        instructions=(
            "Research enterprise knowledge carefully. Use the knowledge-search tool. "
            "Return evidence and document ids. Never invent internal facts."
        ),
        tools=[search_enterprise_knowledge],
    )

    reasoning = Agent(
        name="Reasoning Agent",
        model=settings.openai_model,
        instructions=(
            "Analyze the request and supplied evidence. Identify constraints, risks, "
            "assumptions and a concrete plan. Do not execute external actions."
        ),
    )

    executor = Agent(
        name="Execution Agent",
        model=settings.openai_model,
        instructions=(
            "Execute enterprise actions only when necessary using MCP tools. "
            "Prefer read-only tools. Never claim success unless a tool confirms it. "
            "For risky or irreversible actions, explain that approval is required."
        ),
        mcp_servers=[mcp_server],
        mcp_config={
            "convert_schemas_to_strict": True,
            "include_server_in_tool_names": True,
        },
    )

    reviewer = Agent(
        name="Review Agent",
        model=settings.openai_model,
        instructions=(
            "Review an answer for unsupported claims, missing evidence, unsafe actions, "
            "tenant-data leakage and inconsistency. Return a corrected final answer."
        ),
    )

    supervisor = Agent(
        name="Enterprise Supervisor",
        model=settings.openai_model,
        instructions=(
            "You are the supervisor for an enterprise multi-agent system. "
            "Delegate knowledge questions to research_agent, complex analysis to reasoning_agent, "
            "and external enterprise actions to execution_agent. Use the minimum tools needed. "
            "Keep tenant data isolated. Then produce a concise evidence-based response."
        ),
        tools=[
            research.as_tool(
                tool_name="research_agent",
                tool_description="Research tenant-scoped internal knowledge."
            ),
            reasoning.as_tool(
                tool_name="reasoning_agent",
                tool_description="Perform deep analysis and planning without side effects."
            ),
            executor.as_tool(
                tool_name="execution_agent",
                tool_description="Call enterprise systems through governed MCP tools."
            ),
        ],
    )
    return supervisor, reviewer

async def run_multi_agent(ctx: RunContext, user_input: str, history: list[dict]) -> str:
    async with MCPServerStreamableHttp(
        name="enterprise-java-tools",
        params={
            "url": settings.java_mcp_url,
            "headers": {"X-Tenant-Id": ctx.tenant_id},
            "timeout": 20,
        },
        cache_tools_list=True,
        max_retry_attempts=2,
    ) as mcp:
        supervisor, reviewer = build_agents(ctx, mcp)
        history_text = "\n".join(f"{m['role']}: {m['content']}" for m in history[-12:])
        prompt = f"""Conversation history:
{history_text}

Current user request:
{user_input}
"""
        result = await Runner.run(supervisor, prompt, context={"tenant_id": ctx.tenant_id})
        draft = str(result.final_output)

        reviewed = await Runner.run(
            reviewer,
            f"User request:\n{user_input}\n\nDraft answer:\n{draft}",
            context={"tenant_id": ctx.tenant_id},
        )
        return str(reviewed.final_output)
