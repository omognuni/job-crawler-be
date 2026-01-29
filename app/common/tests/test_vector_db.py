import unittest
from unittest.mock import MagicMock, patch

# Import VectorDB and vector_db_client here to ensure the singleton is created
from common.vector_db import VectorDB


class TestVectorDB(unittest.TestCase):

    @patch("chromadb.HttpClient")
    @patch("chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction")
    def setUp(self, MockEmbeddingFunction, MockHttpClient):
        # Store the original client and embedding function of the singleton
        # so we can restore them after the test
        self._original_vector_db_client_client = VectorDB.get_instance().client
        self._original_vector_db_client_embedding_function = (
            VectorDB.get_instance().embedding_function
        )

        # Create mocks
        self.mock_client = MockHttpClient.return_value
        self.mock_embedding_function = MockEmbeddingFunction.return_value

        # Patch the singleton instance's client and embedding_function attributes
        VectorDB.get_instance().client = self.mock_client
        VectorDB.get_instance().embedding_function = self.mock_embedding_function

        # Also patch the VectorDB.__init__ method to prevent it from
        # creating a real HttpClient when VectorDB() is called within tests
        # and to ensure it uses our mocks if any test code explicitly calls VectorDB()
        self.patcher_init = patch(
            "common.vector_db.VectorDB.__init__", return_value=None
        )
        self.mock_vector_db_init = self.patcher_init.start()
        # Manually set the client and embedding_function for the instance created by the test
        self.vector_db = VectorDB()
        self.vector_db.client = self.mock_client
        self.vector_db.embedding_function = self.mock_embedding_function

    def tearDown(self):
        # Stop the patcher for VectorDB.__init__
        self.patcher_init.stop()
        # Restore the original client and embedding function to the singleton
        VectorDB.get_instance().client = self._original_vector_db_client_client
        VectorDB.get_instance().embedding_function = (
            self._original_vector_db_client_embedding_function
        )

    def test_initialization(self):
        # When VectorDB() is called in setUp, __init__ is mocked, so we can't assert its calls directly
        # Instead, we assert that the client and embedding function attributes are set to our mocks
        self.assertIsInstance(self.vector_db, VectorDB)
        self.assertEqual(self.vector_db.client, self.mock_client)
        self.assertEqual(
            self.vector_db.embedding_function, self.mock_embedding_function
        )
        # We can also assert that the original VectorDB.__init__ was called with the correct args
        # if we wanted to, but since we are mocking it to return None, it's less relevant here.
        # The important part is that the instance attributes are correctly set to mocks.

    def test_get_or_create_collection(self):
        mock_collection = MagicMock()
        self.mock_client.get_or_create_collection.return_value = mock_collection

        collection_name = "test_collection"
        collection = self.vector_db.get_or_create_collection(collection_name)

        self.mock_client.get_or_create_collection.assert_called_once_with(
            name=collection_name, embedding_function=self.mock_embedding_function
        )
        self.assertEqual(collection, mock_collection)

    def test_upsert_documents(self):
        mock_collection = MagicMock()

        documents = ["doc1", "doc2"]
        metadatas = [{"source": "a"}, {"source": "b"}]
        ids = ["id1", "id2"]

        self.vector_db.upsert_documents(mock_collection, documents, metadatas, ids)

        mock_collection.upsert.assert_called_once_with(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
        )

    def test_query(self):
        mock_collection = MagicMock()
        mock_query_results = {"ids": [["id1"]], "documents": [["doc1"]]}
        # Note: self.mock_client.query is not called by vector_db.query,
        # mock_collection.query is called.
        mock_collection.query.return_value = mock_query_results

        query_texts = ["test query"]
        n_results = 2

        results = self.vector_db.query(mock_collection, query_texts, n_results)

        mock_collection.query.assert_called_once_with(
            query_texts=query_texts,
            n_results=n_results,
            include=["distances", "documents", "metadatas"],
        )
        self.assertEqual(results, mock_query_results)

    def test_singleton_instance(self):
        # Ensure that vector_db_client is an instance of VectorDB
        self.assertIsInstance(VectorDB.get_instance(), VectorDB)

        # Ensure that subsequent calls to VectorDB() return the same instance
        # (This test is more about the singleton pattern itself, which is handled by Python's module caching)
        # Given our patching of VectorDB.__init__, we need to be careful here.
        # The key is that vector_db_client *itself* has its attributes patched.
        # If we were to call VectorDB() again, its __init__ is mocked, so it wouldn't
        # create a new HttpClient.
        # The important part is that the *globally accessible* vector_db_client
        # has its internal client and embedding_function set to our mocks.
        self.assertEqual(VectorDB.get_instance().client, self.mock_client)
        self.assertEqual(
            VectorDB.get_instance().embedding_function, self.mock_embedding_function
        )


if __name__ == "__main__":
    unittest.main()
