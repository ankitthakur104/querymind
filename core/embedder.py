import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import os
import sys

# Make sure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.extractor import extract_schema, schema_to_text

# Where ChromaDB will persist its data
CHROMA_PATH = os.path.join(os.path.dirname(__file__), "..", "chroma_store")

# We use a lightweight local model — no API key needed for embeddings
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

def get_chroma_collection():
    """Returns the ChromaDB collection, creating it if needed."""
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_or_create_collection(
        name="schema_tables",
        metadata={"hnsw:space": "cosine"}  # cosine similarity
    )
    return collection


def index_schema():
    """
    Extracts schema → converts to text → embeds → stores in ChromaDB.
    Safe to run multiple times (upserts, not duplicates).
    """
    print("🔍 Extracting schema from database...")
    schema     = extract_schema()
    table_texts = schema_to_text(schema)

    print("🤖 Loading embedding model...")
    model = SentenceTransformer(EMBEDDING_MODEL)

    print("📦 Indexing tables into ChromaDB...")
    collection = get_chroma_collection()

    for table_name, text in table_texts.items():
        embedding = model.encode(text).tolist()

        # upsert = insert if new, update if exists
        collection.upsert(
            ids        =[table_name],
            embeddings =[embedding],
            documents  =[text],
            metadatas  =[{"table": table_name}]
        )
        print(f"  ✅ Indexed: {table_name}")

    print(f"\n✅ Done. {len(table_texts)} tables indexed into ChromaDB.")
    return collection


if __name__ == "__main__":
    index_schema()