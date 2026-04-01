import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.generator import generate_sql
from core.validator import validate_and_execute
from core.retriever import retrieve_relevant_tables, format_schema_for_prompt
import json
import time

# ── Golden test set ────────────────────────────────────────────────
# Each entry: question + expected table(s) + expected row count
# In production you'd have 100-200 of these, stored in a database

GOLDEN_SET = [
    {
        "id":             "G001",
        "question":       "How many customers do we have?",
        "expected_tables": ["customers"],
        "expected_rows":  1,
        "expected_contains": ["total_customers"],
    },
    {
        "id":             "G002",
        "question":       "Who are the top 3 customers by total spending?",
        "expected_tables": ["customers", "orders"],
        "expected_rows":  3,
        "expected_contains": ["name"],
    },
    {
        "id":             "G003",
        "question":       "Which products are low on stock with less than 100 units?",
        "expected_tables": ["products"],
        "expected_rows":  3,
        "expected_contains": ["stock_qty"],
    },
    {
        "id":             "G004",
        "question":       "What is the total revenue from delivered orders?",
        "expected_tables": ["orders"],
        "expected_rows":  1,
        "expected_contains": ["total_revenue"],
    },
    {
        "id":             "G005",
        "question":       "List all product categories and their average price.",
        "expected_tables": ["products"],
        "expected_rows":  3,  # Electronics, Books, Sports, Appliances → 4 categories
        "expected_contains": ["category"],
    },
    {
        "id":             "G006",
        "question":       "Show all orders that are still pending.",
        "expected_tables": ["orders"],
        "expected_rows":  1,
        "expected_contains": ["order_id"],
    },
    {
        "id":             "G007",
        "question":       "Which customer placed the most orders?",
        "expected_tables": ["customers", "orders"],
        "expected_rows":  1,
        "expected_contains": ["name"],
    },
    {
        "id":             "G008",
        "question":       "What is the most expensive product?",
        "expected_tables": ["products"],
        "expected_rows":  1,
        "expected_contains": ["name"],
    },
]


# ── Evaluation logic ───────────────────────────────────────────────

def run_evaluation():
    print("=" * 60)
    print("  QueryMind — Evaluation Suite")
    print("=" * 60)

    results    = []
    passed     = 0
    failed     = 0
    total_time = 0

    for test in GOLDEN_SET:
        print(f"\n[{test['id']}] {test['question']}")
        start = time.time()

        try:
            # Run the full pipeline
            gen     = generate_sql(test["question"])
            sql     = gen["sql"]
            ctx     = format_schema_for_prompt(
                        retrieve_relevant_tables(test["question"])
                      )
            outcome = validate_and_execute(sql, test["question"], ctx)
            elapsed = round((time.time() - start) * 1000)
            total_time += elapsed

            # ── Check 1: did it execute successfully?
            if outcome["status"] != "success":
                raise Exception(f"Execution failed: {outcome.get('reason')}")

            # ── Check 2: correct number of rows?
            row_check = outcome["row_count"] == test["expected_rows"]

            # ── Check 3: expected columns present in results?
            col_check = True
            if outcome["results"]:
                result_keys = set(outcome["results"][0].keys())
                for col in test["expected_contains"]:
                    if col not in result_keys:
                        col_check = False
                        break

            # ── Check 4: expected tables retrieved?
            table_check = any(
                t in gen["retrieved_tables"]
                for t in test["expected_tables"]
            )

            # ── Overall pass/fail
            test_passed = row_check and col_check and table_check

            status_icon = "✅ PASS" if test_passed else "❌ FAIL"
            print(f"  Status     : {status_icon}")
            print(f"  SQL        : {sql[:80].strip()}...")
            print(f"  Rows       : {outcome['row_count']} (expected {test['expected_rows']}) {'✓' if row_check else '✗'}")
            print(f"  Columns    : {list(outcome['results'][0].keys()) if outcome['results'] else []} {'✓' if col_check else '✗'}")
            print(f"  Tables     : {gen['retrieved_tables']} {'✓' if table_check else '✗'}")
            print(f"  Time       : {elapsed}ms")

            if test_passed:
                passed += 1
            else:
                failed += 1

            results.append({
                "id":      test["id"],
                "passed":  test_passed,
                "elapsed": elapsed,
                "sql":     sql,
                "rows":    outcome["row_count"],
            })

        except Exception as e:
            elapsed = round((time.time() - start) * 1000)
            print(f"  Status     : ❌ ERROR")
            print(f"  Error      : {str(e)}")
            failed += 1
            results.append({
                "id":      test["id"],
                "passed":  False,
                "elapsed": elapsed,
                "error":   str(e),
            })

    # ── Summary ────────────────────────────────────────────────────
    total        = passed + failed
    accuracy     = round((passed / total) * 100, 1)
    avg_time     = round(total_time / total)

    print(f"\n{'=' * 60}")
    print(f"  RESULTS SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Passed       : {passed}/{total}")
    print(f"  Failed       : {failed}/{total}")
    print(f"  Accuracy     : {accuracy}%")
    print(f"  Avg latency  : {avg_time}ms per query")
    print(f"{'=' * 60}")

    # Save results to file for tracking over time
    with open("tests/eval_results.json", "w") as f:
        json.dump({
            "accuracy":    accuracy,
            "passed":      passed,
            "failed":      failed,
            "avg_time_ms": avg_time,
            "results":     results,
        }, f, indent=2)

    print(f"\n  Results saved to tests/eval_results.json")
    return accuracy


if __name__ == "__main__":
    run_evaluation()