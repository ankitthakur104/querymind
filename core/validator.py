import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import sqlite3
import sqlparse
from groq import Groq
from dotenv import load_dotenv
from database.schema import DB_PATH

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL  = "llama-3.3-70b-versatile"


def is_safe_query(sql: str) -> tuple[bool, str]:
    """
    Security check — only allow SELECT statements.
    Blocks DROP, DELETE, INSERT, UPDATE, etc.
    This is critical — never let an LLM run write queries.
    """
    parsed = sqlparse.parse(sql)
    if not parsed:
        return False, "Empty query"

    statement = parsed[0]
    query_type = statement.get_type()

    if query_type != "SELECT":
        return False, f"Only SELECT queries allowed. Got: {query_type}"

    # Extra safety — check for dangerous keywords
    dangerous = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE", "TRUNCATE"]
    sql_upper = sql.upper()
    for word in dangerous:
        if word in sql_upper:
            return False, f"Dangerous keyword detected: {word}"

    return True, "OK"


def validate_sql_syntax(sql: str) -> tuple[bool, str]:
    """
    Tries to run the query with EXPLAIN to catch syntax errors
    without actually executing it.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(f"EXPLAIN QUERY PLAN {sql}")
        conn.close()
        return True, "OK"
    except sqlite3.Error as e:
        return False, str(e)


def auto_correct_sql(sql: str, error: str, original_question: str, schema_context: str) -> str:
    fix_prompt = f"""You generated this SQL query:
{sql}

It produced this error:
{error}

The original question was:
{original_question}

The available schema is:
{schema_context}

Please fix the SQL query. Output ONLY the corrected SQL, no explanation, no backticks."""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": fix_prompt}],
        temperature=0,
        max_tokens=512,
    )
    fixed = response.choices[0].message.content.strip()
    fixed = fixed.replace("```sql", "").replace("```", "").strip()
    return fixed


def execute_sql(sql: str) -> tuple[bool, list | str]:
    """
    Executes the SQL and returns results.
    Returns (success, results_or_error_message)
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        conn.close()

        # Convert Row objects to plain dicts
        results = [dict(row) for row in rows]
        return True, results

    except sqlite3.Error as e:
        return False, str(e)


def validate_and_execute(
    sql: str,
    question: str,
    schema_context: str,
    max_retries: int = 2
) -> dict:
    """
    Full validation pipeline:
    1. Safety check (no write queries)
    2. Syntax check via EXPLAIN
    3. Auto-correct if syntax error (up to max_retries times)
    4. Execute and return results

    Returns dict with status, sql, results, and any corrections made.
    """
    corrections = []

    # Step 1: safety check
    safe, reason = is_safe_query(sql)
    if not safe:
        return {
            "status":      "blocked",
            "reason":      reason,
            "sql":         sql,
            "results":     [],
            "corrections": corrections,
        }

    # Step 2 & 3: validate + auto-correct loop
    current_sql = sql
    for attempt in range(max_retries + 1):
        valid, error = validate_sql_syntax(current_sql)

        if valid:
            break  # SQL is clean, move to execution

        print(f"  ⚠️  Syntax error (attempt {attempt+1}): {error}")

        if attempt < max_retries:
            print(f"  🔄 Auto-correcting...")
            current_sql = auto_correct_sql(
                current_sql, error, question, schema_context
            )
            corrections.append({
                "attempt": attempt + 1,
                "error":   error,
                "fixed_sql": current_sql
            })
        else:
            return {
                "status":      "error",
                "reason":      f"Could not fix after {max_retries} attempts: {error}",
                "sql":         current_sql,
                "results":     [],
                "corrections": corrections,
            }

    # Step 4: execute
    success, results = execute_sql(current_sql)

    if success:
        return {
            "status":      "success",
            "sql":         current_sql,
            "results":     results,
            "row_count":   len(results),
            "corrections": corrections,
        }
    else:
        return {
            "status":      "error",
            "reason":      results,  # results holds error string on failure
            "sql":         current_sql,
            "results":     [],
            "corrections": corrections,
        }


if __name__ == "__main__":
    # Test the full pipeline end to end
    from core.generator import generate_sql
    from core.retriever import format_schema_for_prompt, retrieve_relevant_tables

    test_questions = [
        "Who are the top 3 customers by total spending?",
        "Which products are low on stock?",
        "What is the total revenue from delivered orders?",
    ]

    for question in test_questions:
        print(f"\n{'='*55}")
        print(f"Q: {question}")

        # Generate SQL
        result = generate_sql(question)
        sql = result["sql"]
        schema_ctx = format_schema_for_prompt(
            retrieve_relevant_tables(question)
        )

        print(f"Generated SQL:\n{sql}")

        # Validate + execute
        outcome = validate_and_execute(sql, question, schema_ctx)

        print(f"Status     : {outcome['status']}")
        if outcome["status"] == "success":
            print(f"Row count  : {outcome['row_count']}")
            for row in outcome["results"]:
                print(f"  {row}")
        else:
            print(f"Error      : {outcome.get('reason')}")