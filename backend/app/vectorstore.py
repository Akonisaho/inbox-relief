from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.config import QDRANT_URL

EMBEDDING_DIM = 768  # nomic-embed-text output size

_client = QdrantClient(url=QDRANT_URL)


def _collection_name(tenant_id: int) -> str:
    return f"tenant_{tenant_id}_emails"


def ensure_collection(tenant_id: int) -> None:
    name = _collection_name(tenant_id)
    if not _client.collection_exists(name):
        _client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
        )


def upsert_email_vector(tenant_id: int, email_id: int, vector: list[float], payload: dict) -> None:
    ensure_collection(tenant_id)
    _client.upsert(
        collection_name=_collection_name(tenant_id),
        points=[PointStruct(id=email_id, vector=vector, payload=payload)],
    )


def search_similar(tenant_id: int, vector: list[float], limit: int = 5) -> list[dict]:
    name = _collection_name(tenant_id)
    if not _client.collection_exists(name):
        return []
    results = _client.query_points(collection_name=name, query=vector, limit=limit).points
    return [{"id": r.id, "score": r.score, **r.payload} for r in results]
