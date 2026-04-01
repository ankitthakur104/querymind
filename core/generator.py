import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from groq import Groq
from dotenv import load_dotenv
from core.retriever import retrieve_relevant_tables, format_schema_for_prompt

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL  = "llama-3.3-70b-versatile"  # best free model on Groq for SQL

# ── Few-shot examples ──────────────────────────────────────────────
# These teach the LLM your exact schema and expected SQL style.
# In production you'd store these in a database and keep adding more.

FEW_SHOT_EXAMPLES = """
## Examples

Q: How many customers do we have?
SQL:
SELECT COUNT(*) AS total_customers
FROM customers;

Q: List all products with their prices sorted by price descending.
SQL:
SELECT name, category, price
FROM products
ORDER BY price DESC;

Q: What are the total sales per customer?
SQL:
SELECT c.name, SUM(o.total_amount) AS total_spent
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.name
ORDER BY total_spent DESC;

Q: Show all delivered orders with customer names.
SQL:
SELECT c.name, o.order_id, o.order_date, o.total_amount
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
WHERE o.status = 'delivered';

Q: Which products have less than 100 items in stock?
SQL:
SELECT name, category, stock_qty
FROM products
WHERE stock_qty < 100
ORDER BY stock_qty ASC;
"""

# ── System prompt ──────────────────────────────────────────────────
# This is the most important part of prompt engineering.
# Every rule here prevents a class of LLM mistakes.

SYSTEM_PROMPT = """You are an expert SQLite SQL generator.

Your job is to convert natural language questions into correct SQLite SQL queries.

Rules you must follow:
1. Output ONLY the raw SQL query — no explanation, no markdown, no backticks, no commentary.
2. Always use explicit column names — never use SELECT *.
3. Always use table aliases for JOIN queries (c for customers, o for orders, etc).
4. Use only the tables and columns provided in the schema — never invent columns.
5. For aggregations, always include a GROUP BY clause when needed.
6. Add ORDER BY to ranking or "top N" questions.
7. Use single quotes for string values (SQLite standard).
8. If the question cannot be answered from the given schema, reply with exactly: UNABLE_TO_ANSWER
"""


def generate_sql(question: str, top_k: int = 2) -> dict:
    """
    Full pipeline: question → retrieve schema → build prompt → LLM → SQL.

    Returns dict with:
      - question: original question
      - sql: generated SQL string
      - retrieved_tables: which tables were used
      - prompt: the full prompt sent to LLM (useful for debugging)
    """

    # Step 1: retrieve relevant tables via RAG
    retrieved = retrieve_relevant_tables(question, top_k=top_k)
    schema_context = format_schema_for_prompt(retrieved)
    table_names = [r["table"] for r in retrieved]

    # Step 2: build the full prompt
    prompt = f"""{SYSTEM_PROMPT}

{FEW_SHOT_EXAMPLES}

## Your Task

### Schema (use ONLY these tables):
{schema_context}

### Question:
{question}

SQL:"""

    # Step 3: call Groq (replaces Gemini call)
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0,       # 0 = deterministic, important for SQL
        max_tokens=512,
    )
    sql = response.choices[0].message.content.strip()

    # Step 4: clean up common LLM formatting habits
    sql = sql.replace("```sql", "").replace("```", "").strip()

    return {
        "question":         question,
        "sql":              sql,
        "retrieved_tables": table_names,
        "prompt":           prompt,
    }


if __name__ == "__main__":
    test_questions = [
        "Who are the top 3 customers by total spending?",
        "Which products are low on stock (less than 100 units)?",
        "Show me all cancelled orders with customer names.",
        "What is the total revenue from delivered orders?",
        "Which product category has the highest average price?",
    ]

    for question in test_questions:
        print(f"\n{'='*55}")
        print(f"Q: {question}")
        result = generate_sql(question)
        print(f"Tables used : {result['retrieved_tables']}")
        print(f"Generated SQL:\n{result['sql']}")