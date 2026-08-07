from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ASCENDING, DESCENDING

from bot.alerts.models import Alert, AlertCreate, date_to_utc_datetime

DEFAULT_DB = "ar_plus_helper"
DEFAULT_COLLECTION = "alerts"


class AlertRepository:
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
        self._collection().create_index([("user_id", ASCENDING)])

    def list_all(self) -> list[Alert]:
        alerts: list[Alert] = []
        for doc in self._collection().find({}):
            alert = Alert.from_doc(doc)
            if alert is not None:
                alerts.append(alert)
        return alerts

    def list_by_user(self, user_id: str) -> list[Alert]:
        cursor = self._collection().find({"user_id": str(user_id)}).sort(
            "created_at", DESCENDING
        )
        alerts: list[Alert] = []
        for doc in cursor:
            alert = Alert.from_doc(doc)
            if alert is not None:
                alerts.append(alert)
        return alerts

    def get_for_user(self, user_id: str, alert_id: str) -> Alert | None:
        try:
            oid = ObjectId(alert_id)
        except InvalidId:
            return None
        doc = self._collection().find_one({"_id": oid, "user_id": str(user_id)})
        if doc is None:
            return None
        return Alert.from_doc(doc)

    def create(self, user_id: str, data: AlertCreate) -> str:
        doc = {
            "user_id": str(user_id),
            "origin": data.origin,
            "destination": data.destination,
            "date_min": date_to_utc_datetime(data.date_min),
            "date_max": date_to_utc_datetime(data.date_max),
            "max_price": data.max_price,
            "cabin_type": data.cabin_type,
            "created_at": datetime.now(timezone.utc),
        }
        result = self._collection().insert_one(doc)
        return str(result.inserted_id)

    def delete_for_user(self, user_id: str, alert_id: str) -> bool:
        try:
            oid = ObjectId(alert_id)
        except InvalidId:
            return False
        result = self._collection().delete_one(
            {"_id": oid, "user_id": str(user_id)}
        )
        return result.deleted_count == 1

    def close(self) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None
