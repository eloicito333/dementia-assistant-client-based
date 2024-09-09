from dotenv import load_dotenv
load_dotenv()

import os
from qdrant_client import QdrantClient
from qdrant_client.http import VectorParams, Distance

class QdrantDBAdapter:
    def __init__(self):
        pass

class DBAdapter:
    def _create_speacked_data_db(self):
        if not self.client.collection_exists("my_collection"):
            self.client.create_collection(
                collection_name="my_collection",
                vectors_config=VectorParams(size=256, distance=Distance.COSINE),
            )

    def __init__(self, user_id, url="http://localhost:6333", api_key=os.getenv('QDRANT_API_KEY')):
        self.api_key = api_key
        self.client = QdrantClient(url=url, api_key=self.api_key)



db_adapter = DBAdapter(url="https://ea18c967-c844-4442-adb8-4439ea64e3d7.europe-west3-0.gcp.cloud.qdrant.io")