from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from .config import settings
from .models import KnowledgeDocument

client = AsyncOpenAI(api_key=settings.openai_api_key)

async def embed(text: str) -> list[float]:
    response = await client.embeddings.create(model=settings.embedding_model, input=text)
    return response.data[0].embedding

async def ingest(db: AsyncSession, tenant_id: str, documents):
    for doc in documents:
        vector = await embed(doc.text)
        existing = await db.get(KnowledgeDocument, {"id": doc.id, "tenant_id": tenant_id})
        if existing:
            existing.text, existing.doc_metadata, existing.embedding = doc.text, doc.metadata, vector
        else:
            db.add(KnowledgeDocument(
                id=doc.id, tenant_id=tenant_id, text=doc.text,
                doc_metadata=doc.metadata, embedding=vector))
    await db.commit()

async def search(db: AsyncSession, tenant_id: str, query: str, k: int = 5) -> list[dict]:
    vector = await embed(query)
    distance = KnowledgeDocument.embedding.cosine_distance(vector)
    stmt = (select(KnowledgeDocument, distance.label("distance"))
            .where(KnowledgeDocument.tenant_id == tenant_id)
            .order_by(distance).limit(k))
    rows = (await db.execute(stmt)).all()
    return [{"id": d.id, "text": d.text, "metadata": d.doc_metadata,
             "score": float(1 - dist)} for d, dist in rows]
