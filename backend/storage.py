"""
Document store.
Uses Azure Cosmos DB when COSMOS_ENDPOINT + COSMOS_KEY are set.
Falls back to a local JSON file for local development.
"""
import json
from pathlib import Path
from typing import Optional, List
from config import settings


class CosmosStore:
    def __init__(self):
        from azure.cosmos import CosmosClient
        self.client    = CosmosClient(settings.cosmos_endpoint, settings.cosmos_key)
        self.db        = self.client.get_database_client(settings.cosmos_database)
        self.container = self.db.get_container_client(settings.cosmos_container)

    def save(self, doc: dict):
        self.container.upsert_item(doc)

    def get(self, doc_id: str) -> Optional[dict]:
        try:
            items = list(self.container.query_items(
                query="SELECT * FROM c WHERE c.id = @id",
                parameters=[{"name": "@id", "value": doc_id}],
                enable_cross_partition_query=True,
            ))
            return items[0] if items else None
        except Exception:
            return None

    def list_all(self) -> List[dict]:
        try:
            return list(self.container.query_items(
                query="SELECT * FROM c ORDER BY c._ts DESC",
                enable_cross_partition_query=True,
            ))
        except Exception:
            return []


class LocalStore:
    def __init__(self, filepath: str = "documents.json"):
        self.path = Path(filepath)
        if not self.path.exists():
            self.path.write_text("[]")

    def _load(self) -> List[dict]:
        try:
            return json.loads(self.path.read_text())
        except Exception:
            return []

    def _write(self, docs: List[dict]):
        self.path.write_text(json.dumps(docs, indent=2, default=str))

    def save(self, doc: dict):
        docs = self._load()
        idx  = next((i for i, d in enumerate(docs) if d["id"] == doc["id"]), None)
        if idx is not None:
            docs[idx] = doc
        else:
            docs.insert(0, doc)
        self._write(docs)

    def get(self, doc_id: str) -> Optional[dict]:
        return next((d for d in self._load() if d["id"] == doc_id), None)

    def list_all(self) -> List[dict]:
        return self._load()


def get_store():
    if settings.use_cosmos:
        try:
            return CosmosStore()
        except Exception as e:
            print(f"Cosmos unavailable ({e}), using local store")
    return LocalStore()
