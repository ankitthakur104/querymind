import sqlite3
import json
from database.schema import DB_PATH

def extract_schema(db_path: str = DB_PATH) -> dict:
    """
    Extracts full schema metadata from SQLite database.
    Returns a dict: { table_name: { columns, foreign_keys, sample_rows, description } }
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get all table names
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row["name"] for row in cursor.fetchall()]

    schema = {}

    for table in tables:
        # Column info
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [
            {
                "name":     col["name"],
                "type":     col["type"],
                "not_null": bool(col["notnull"]),
                "pk":       bool(col["pk"])
            }
            for col in cursor.fetchall()
        ]

        # Foreign keys
        cursor.execute(f"PRAGMA foreign_key_list({table})")
        foreign_keys = [
            {
                "column":      fk["from"],
                "references":  f"{fk['table']}.{fk['to']}"
            }
            for fk in cursor.fetchall()
        ]

        # Sample rows (3 rows, safe)
        cursor.execute(f"SELECT * FROM {table} LIMIT 3")
        rows = cursor.fetchall()
        sample_rows = [dict(row) for row in rows]

        schema[table] = {
            "columns":      columns,
            "foreign_keys": foreign_keys,
            "sample_rows":  sample_rows,
        }

    conn.close()
    return schema


def schema_to_text(schema: dict) -> dict[str, str]:
    """
    Converts schema dict into human-readable text per table.
    This is what gets embedded into ChromaDB.
    """
    table_texts = {}

    for table, info in schema.items():
        lines = [f"Table: {table}"]
        lines.append("Columns:")
        for col in info["columns"]:
            pk_tag  = " [PRIMARY KEY]"  if col["pk"]       else ""
            nn_tag  = " NOT NULL"        if col["not_null"] else ""
            lines.append(f"  - {col['name']} ({col['type']}{pk_tag}{nn_tag})")

        if info["foreign_keys"]:
            lines.append("Foreign keys:")
            for fk in info["foreign_keys"]:
                lines.append(f"  - {fk['column']} → {fk['references']}")

        if info["sample_rows"]:
            lines.append("Sample data:")
            for row in info["sample_rows"][:2]:
                lines.append(f"  {row}")

        table_texts[table] = "\n".join(lines)

    return table_texts


if __name__ == "__main__":
    schema = extract_schema()
    texts  = schema_to_text(schema)
    for table, text in texts.items():
        print(f"\n{'='*50}")
        print(text)