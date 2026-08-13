import sys
from pathlib import Path
from unittest import TestCase, mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot.filters.models import Filter
from bot.filters.repository import FilterRepository


class FilterModelTests(TestCase):
    def test_from_doc_parses_valid_document(self):
        doc = {
            "_id": {"$oid": "698cdfa4ef42c96e7b425f42"},
            "user_id": "281943056",
            "preferences": {
                "limit": 15,
            },
        }
        f = Filter.from_doc(doc)
        self.assertIsNotNone(f)
        assert f is not None
        self.assertEqual(f.id, "698cdfa4ef42c96e7b425f42")
        self.assertEqual(f.user_id, "281943056")
        self.assertEqual(f.limit, 15)

    def test_from_doc_rejects_missing_preferences(self):
        doc = {
            "_id": "some_id",
            "user_id": "281943056",
        }
        self.assertIsNone(Filter.from_doc(doc))

    def test_from_doc_rejects_invalid_limit(self):
        doc = {
            "user_id": "281943056",
            "preferences": {
                "limit": 50,
            },
        }
        self.assertIsNone(Filter.from_doc(doc))


class FilterRepositoryTests(TestCase):
    def setUp(self):
        self.mock_client = mock.MagicMock()
        self.mock_db = mock.MagicMock()
        self.mock_collection = mock.MagicMock()
        self.mock_client.__getitem__.return_value = self.mock_db
        self.mock_db.__getitem__.return_value = self.mock_collection

        self.repo = FilterRepository(
            mongo_uri="mongodb://localhost:27017",
            client=self.mock_client,
        )

    def test_ensure_indexes(self):
        self.repo.ensure_indexes()
        self.mock_collection.create_index.assert_called_once()

    def test_get_by_user_returns_filter_when_exists(self):
        self.mock_collection.find_one.return_value = {
            "_id": "id123",
            "user_id": "user123",
            "preferences": {"limit": 20},
        }
        res = self.repo.get_by_user("user123")
        self.assertIsNotNone(res)
        assert res is not None
        self.assertEqual(res.limit, 20)
        self.mock_collection.find_one.assert_called_once_with({"user_id": "user123"})

    def test_get_by_user_returns_none_when_missing(self):
        self.mock_collection.find_one.return_value = None
        res = self.repo.get_by_user("user123")
        self.assertIsNone(res)

    def test_set_for_user_calls_update_one(self):
        self.mock_collection.update_one.return_value = mock.Mock(upserted_id="new_id")
        res = self.repo.set_for_user("user123", 15)
        self.assertEqual(res, "new_id")
        self.mock_collection.update_one.assert_called_once()

    def test_delete_for_user_calls_update_one(self):
        self.mock_collection.update_one.return_value = mock.Mock(modified_count=1)
        res = self.repo.delete_for_user("user123")
        self.assertTrue(res)
        self.mock_collection.update_one.assert_called_once_with(
            {"user_id": "user123"},
            {"$unset": {"preferences.limit": ""}}
        )
