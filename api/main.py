from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import time
import logging

from core.generator import generate_sql
from core.validator import validate_and_execute
from core.retriever import retrieve_relevant_tables, format_schema_for_prompt

load_dotenv()

# ── Logging setup ──────────────────────────────────────────────────
# In production this would go to a log aggregator like Datadog
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

# ── App setup ──────────────────────────────────────────────────────
app = FastAPI(
    title="QueryMind — Text to SQL API",
    description="Convert natural language questions into SQL and get results.",
    version="1.0.0",
)
app.mount("/static", StaticFiles(directory="ui"), name="static")

@app.get("/ui")
def serve_ui():
    return FileResponse("ui/index.html")

# Allow all origins for local development
# In production: restrict to your frontend domain only
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Simple in-memory rate limiter ──────────────────────────────────
# Tracks requests per IP. In production use Redis instead.
request_counts: dict[str, list[float]] = {}
RATE_LIMIT     = 10   # max requests
RATE_WINDOW    = 60   # per 60 seconds

def is_rate_limited(ip: str) -> bool:
    now      = time.time()
    window   = request_counts.get(ip, [])
    # Keep only timestamps within the current window
    window   = [t for t in window if now - t < RATE_WINDOW]
    if len(window) >= RATE_LIMIT:
        return True
    window.append(now)
    request_counts[ip] = window
    return False


# ── Request / Response models ──────────────────────────────────────
class QueryRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=5,
        max_length=500,
        example="Who are the top 3 customers by total spending?"
    )
    top_k: int = Field(
        default=2,
        ge=1,
        le=4,
        description="Number of tables to retrieve from vector store"
    )

class QueryResponse(BaseModel):
    question:         str
    sql:              str
    results:          list[dict]
    row_count:        int
    retrieved_tables: list[str]
    execution_time_ms: float
    status:           str
    corrections_made: int


class HealthResponse(BaseModel):
    status:  str
    version: str
    message: str


# ── Routes ─────────────────────────────────────────────────────────

@app.get("/", response_model=HealthResponse)
def root():
    return {
        "status":  "ok",
        "version": "1.0.0",
        "message": "QueryMind API is running."
    }


@app.get("/health", response_model=HealthResponse)
def health():
    return {
        "status":  "ok",
        "version": "1.0.0",
        "message": "All systems operational."
    }


@app.post("/query", response_model=QueryResponse)
async def query(request: Request, body: QueryRequest):
    """
    Main endpoint. Takes a natural language question,
    returns SQL + executed results.
    """
    # Rate limiting
    client_ip = request.client.host
    if is_rate_limited(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Max 10 per minute."
        )

    start_time = time.time()
    logger.info(f"Query received | IP: {client_ip} | Question: {body.question}")

    try:
        # Step 1: generate SQL via RAG + LLM
        gen_result = generate_sql(body.question, top_k=body.top_k)
        sql        = gen_result["sql"]

        # Step 2: check if LLM couldn't answer
        if sql.strip() == "UNABLE_TO_ANSWER":
            raise HTTPException(
                status_code=422,
                detail="Question cannot be answered from the available schema."
            )

        # Step 3: validate + execute
        schema_ctx = format_schema_for_prompt(
            retrieve_relevant_tables(body.question, top_k=body.top_k)
        )
        outcome = validate_and_execute(sql, body.question, schema_ctx)

        # Step 4: handle execution errors
        if outcome["status"] == "blocked":
            raise HTTPException(
                status_code=403,
                detail=f"Query blocked: {outcome['reason']}"
            )

        if outcome["status"] == "error":
            raise HTTPException(
                status_code=500,
                detail=f"SQL execution failed: {outcome['reason']}"
            )

        # Step 5: build response
        elapsed_ms = round((time.time() - start_time) * 1000, 2)

        logger.info(
            f"Query success | {elapsed_ms}ms | "
            f"tables={gen_result['retrieved_tables']} | "
            f"rows={outcome['row_count']}"
        )

        return QueryResponse(
            question          = body.question,
            sql               = outcome["sql"],
            results           = outcome["results"],
            row_count         = outcome["row_count"],
            retrieved_tables  = gen_result["retrieved_tables"],
            execution_time_ms = elapsed_ms,
            status            = "success",
            corrections_made  = len(outcome["corrections"]),
        )

    except HTTPException:
        raise  # re-raise our own HTTP exceptions as-is

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.get("/schema")
def get_schema():
    """
    Returns the list of available tables in the database.
    Useful for frontend to show users what data exists.
    """
    from core.extractor import extract_schema
    schema = extract_schema()
    return {
        "tables": list(schema.keys()),
        "table_count": len(schema)
    }