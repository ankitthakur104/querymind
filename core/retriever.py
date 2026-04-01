import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sentence_transformers import SentenceTransformer
from core.embedder import get_chroma_collection, EMBEDDING_MODEL
# Load once at module level — not inside the function
_model = SentenceTransformer(EMBEDDING_MODEL)

def retrieve_relevant_tables(question: str, top_k: int = 2) -> list[dict]:
    """
    Given a natural language question, returns the top-K most
    relevant table descriptions from ChromaDB.

    Returns a list of dicts: [{ "table": name, "description": text, "score": float }]
    """
    
    collection = get_chroma_collection()

    # Embed the question using the same model
    question_embedding = _model.encode(question).tolist()

    # Search ChromaDB
    results = collection.query(
        query_embeddings=[question_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"]
    )

    retrieved = []
    for i in range(len(results["ids"][0])):
        retrieved.append({
            "table":       results["metadatas"][0][i]["table"],
            "description": results["documents"][0][i],
            "score":       round(1 - results["distances"][0][i], 3)
            # cosine distance → similarity score (higher = more relevant)
        })

    return retrieved


def format_schema_for_prompt(retrieved_tables: list[dict]) -> str:
    """
    Formats retrieved tables into a clean string
    that gets injected into the LLM prompt.
    """
    lines = ["### Relevant Database Tables\n"]
    for item in retrieved_tables:
        lines.append(item["description"])
        lines.append("")  # blank line between tables
    return "\n".join(lines)


if __name__ == "__main__":
    # Test with sample questions
    test_questions = [
        "Who are the top customers by total spending?",
        "Which products are low on stock?",
        "Show me all cancelled orders",
        "What is the most popular product category?",
    ]

    for question in test_questions:
        print(f"\n{'='*55}")
        print(f"Question : {question}")
        results = retrieve_relevant_tables(question, top_k=2)
        print(f"Retrieved: {[r['table'] for r in results]}")
        for r in results:
            print(f"  → {r['table']} (similarity: {r['score']})")