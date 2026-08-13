from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ASCENDING

from bot.filters.models import Filter

DEFAULT_DB = "ar_plus_helper"
DEFAULT_COLLECTION = "users"


class FilterRepository:
    def __init__(
        self,
        mongo_uri: str | None = None,
        *,
        db_name: str = DEFAULT_DB,
        collection_name: str = DEFAULT_COLLECTION,
        client: Any | None = None,
    ):
        self.mongo_uri = (mongo_uri or os.getenv("MONGODB_URI") or "").strip()
        self.db_name = db_name
        self.collection_name = collection_name
        self._client = client
        self._owns_client = client is None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self.mongo_uri:
            raise RuntimeError("Missing MONGODB_URI")
        from pymongo import MongoClient

        self._client = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=10_000)
        return self._client

    def _collection(self) -> Any:
        return self._get_client()[self.db_name][self.collection_name]

    def ensure_indexes(self) -> None:
        self._collection().create_index([("user_id", ASCENDING)], unique=True)

    def get_by_user(self, user_id: str) -> Filter | None:
        doc = self._collection().find_one({"user_id": str(user_id)})
        if doc is None:
            return None
        return Filter.from_doc(doc)

    def get_by_id(self, user_id: str, filter_id: str) -> Filter | None:
        try:
            oid = ObjectId(filter_id)
        except InvalidId:
            return None
        doc = self._collection().find_one({"_id": oid, "user_id": str(user_id)})
        if doc is None:
            return None
        return Filter.from_doc(doc)

    def set_for_user(self, user_id: str, limit: int) -> str:
        query = {"user_id": str(user_id)}
        update = {
            "$set": {
                "user_id": str(user_id),
                "preferences.limit": limit,
                "updated_at": datetime.now(timezone.utc),
            }
        }
        result = self._collection().update_one(query, update, upsert=True)
        if result.upserted_id:
            return str(result.upserted_id)
        existing = self._collection().find_one(query, {"_id": 1})
        return str(existing["_id"]) if existing else ""

    def delete_for_user(self, user_id: str) -> bool:
        result = self._collection().update_one(
            {"user_id": str(user_id)},
            {"$unset": {"preferences.limit": ""}}
        )
        return result.modified_count == 1

    def delete_by_id(self, user_id: str, filter_id: str) -> bool:
        try:
            oid = ObjectId(filter_id)
        except InvalidId:
            return False
        result = self._collection().update_one(
            {"_id": oid, "user_id": str(user_id)},
            {"$unset": {"preferences.limit": ""}}
        )
        return result.modified_count == 1

    def close(self) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None
