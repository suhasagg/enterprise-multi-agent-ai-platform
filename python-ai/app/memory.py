from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from .models import Conversation, Message

class MemoryStore:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def ensure_conversation(self, session_id: str, tenant_id: str):
        conv = await self.db.get(Conversation, session_id)
        if conv is None:
            self.db.add(Conversation(id=session_id, tenant_id=tenant_id))
            await self.db.commit()
        elif conv.tenant_id != tenant_id:
            raise PermissionError("session belongs to another tenant")

    async def append(self, session_id: str, role: str, content: str):
        self.db.add(Message(conversation_id=session_id, role=role, content=content))
        await self.db.commit()

    async def history(self, session_id: str, limit: int = 20) -> list[dict]:
        q = (select(Message)
             .where(Message.conversation_id == session_id)
             .order_by(Message.id.desc()).limit(limit))
        rows = list((await self.db.scalars(q)).all())
        rows.reverse()
        return [{"role": x.role, "content": x.content} for x in rows]
