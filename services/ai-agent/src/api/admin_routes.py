import os
import re
import time
from typing import Any, List, Optional
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from groq import AsyncGroq
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()
router = APIRouter(prefix="/api/v1/admin", tags=["Admin BI & Text-to-SQL"])

groq_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
SQL_MODEL = "openai/gpt-oss-20b"  # Fast, strong at Postgres SQL

# 1. Grounding Schema Prompt
DB_SCHEMA_PROMPT = """
You are a senior PostgreSQL data analyst for a payment operations platform (UPI Sentinel).
Convert the user's natural-language question into a SINGLE valid, read-only PostgreSQL SELECT query.

DATABASE SCHEMA:
1. transaction (
     txn_id VARCHAR PRIMARY KEY,
     rail VARCHAR,              -- 'UPI', 'IMPS', 'NEFT', 'RTGS'
     amount_inr NUMERIC,
     current_status VARCHAR,    -- 'SUCCESS', 'PENDING', 'FAILED'
     created_at TIMESTAMP
   )
2. txn_event (
     event_id SERIAL PRIMARY KEY,
     txn_id VARCHAR REFERENCES transaction(txn_id),
     status VARCHAR,            -- 'DEBITED', 'PENDING', 'SUCCESS', 'FAILED'
     response_code VARCHAR,     -- e.g. 'NETWORK_TIMEOUT', 'BENEFICIARY_OFFLINE'
     event_time TIMESTAMP
   )
3. approval_request (
     id SERIAL PRIMARY KEY,
     run_id VARCHAR,
     action_type VARCHAR,       -- 'REFUND', 'DISPUTE', 'ESCALATE'
     payload JSONB,
     status VARCHAR,            -- 'PENDING', 'APPROVED', 'REJECTED'
     created_at TIMESTAMP
   )
4. audit_log (
     id SERIAL PRIMARY KEY,
     event_type VARCHAR,
     actor_role VARCHAR,
     details JSONB,
     created_at TIMESTAMP
   )

STRICT RULES:
- Output ONLY raw PostgreSQL SQL. No markdown fences (```sql), no explanations, no comments.
- Only generate SELECT or WITH ... SELECT queries.
- Never use INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, or GRANT.
- Always use explicit column aliases for aggregations (e.g., SUM(amount_inr) AS total_amount_inr).
- Default to LIMIT 50 unless the user asks for a smaller number.
"""

# 2. Guardrail: Static SQL Validator
FORBIDDEN_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|EXECUTE|COPY|PG_SLEEP)\b",
    re.IGNORECASE,
)


def validate_and_sanitize_sql(raw_sql: str) -> str:
    # Strip markdown code fences if the LLM accidentally includes them
    sql = re.sub(r"^```(?:sql)?\s*|\s*```$", "", raw_sql.strip(), flags=re.IGNORECASE).strip()

    # Block multiple statements (semicolon chaining)
    sql = sql.rstrip(";").strip()
    if ";" in sql:
        raise ValueError("Multiple SQL statements are not allowed.")

    # Must start with SELECT or WITH (CTE)
    if not re.match(r"^(SELECT|WITH)\b", sql, re.IGNORECASE):
        raise ValueError("Only read-only SELECT queries are permitted.")

    # Block any mutating or dangerous keywords
    if FORBIDDEN_KEYWORDS.search(sql):
        raise ValueError("Blocked: Query contains forbidden write/DDL keywords.")

    # Auto-enforce LIMIT 50 if no LIMIT clause is present
    if not re.search(r"\bLIMIT\s+\d+\b", sql, re.IGNORECASE):
        sql = f"{sql} LIMIT 50"

    return sql


class TextToSQLRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=500)


class TextToSQLResponse(BaseModel):
    prompt: str
    generated_sql: str
    columns: List[str]
    rows: List[dict[str, Any]]
    row_count: int
    execution_ms: float

def execute_read_only_query(sql: str) -> tuple[List[str], List[dict[str, Any]], float]:
    """Executes SQL inside a strict READ ONLY transaction with a 3s timeout."""
    db_url = os.getenv("DB_CONN")
    if db_url:
        conn = psycopg2.connect(db_url)
    else:
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            dbname=os.getenv("POSTGRES_DB", "postgres"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "postgres"),
        )

    start = time.perf_counter()
    try:
        conn.autocommit = False
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Database-level read-only + timeout guardrails
            cur.execute("SET TRANSACTION READ ONLY;")
            cur.execute("SET LOCAL statement_timeout = '3000ms';")
            cur.execute(sql)

            columns = [desc[0] for desc in cur.description] if cur.description else []
            rows = [dict(row) for row in cur.fetchall()]
        conn.rollback()  # Always rollback read-only exploration
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        return columns, rows, elapsed_ms
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

@router.post("/text-to-sql", response_model=TextToSQLResponse)
async def text_to_sql(
    req: TextToSQLRequest,
    x_user_role: Optional[str] = Header(default="l1_support", alias="X-User-Role"),
):
    # RBAC Guardrail: Restrict raw SQL exploration to ops_lead (or allow demo read-only)
    if x_user_role != "ops_lead":
        raise HTTPException(
            status_code=403,
            detail="RBAC Blocked: Switch role to 'ops_lead' to run Admin Text-to-SQL queries.",
        )

    # 1. Generate SQL via Groq
    try:
        completion = await groq_client.chat.completions.create(
            model=SQL_MODEL,
            messages=[
                {"role": "system", "content": DB_SCHEMA_PROMPT},
                {"role": "user", "content": req.prompt},
            ],
            temperature=0.0,
        )
        raw_sql = completion.choices[0].message.content or ""
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM SQL generation failed: {str(e)}")

    # 2. Validate SQL against read-only guardrails
    try:
        safe_sql = validate_and_sanitize_sql(raw_sql)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"SQL Security Guardrail Triggered: {str(e)}")

    # 3. Execute safely in Postgres
    try:
        columns, rows, elapsed_ms = execute_read_only_query(safe_sql)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"SQL Execution Error: {str(e)} | Generated SQL: {safe_sql}",
        )

    return TextToSQLResponse(
        prompt=req.prompt,
        generated_sql=safe_sql,
        columns=columns,
        rows=rows,
        row_count=len(rows),
        execution_ms=elapsed_ms,
    )

@router.get("/metrics")
async def get_admin_metrics(
    x_user_role: Optional[str] = Header(default="l1_support", alias="X-User-Role"),
):
    """Returns aggregated BI metrics for the Admin Dashboard (KPIs + Charts)."""
    db_url = os.getenv("DB_CONN") or os.getenv("DATABASE_URL")
    conn = psycopg2.connect(db_url) if db_url else psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "sentinel"),
        user=os.getenv("POSTGRES_USER", "sentinel"),
        password=os.getenv("POSTGRES_PASSWORD", "sentinel_dev"),
    )

    try:
        conn.autocommit = False
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET TRANSACTION READ ONLY;")
            cur.execute("SET LOCAL statement_timeout = '3000ms';")

            # 1. KPI Summary
            cur.execute("""
                SELECT
                    COUNT(*)::int AS total_txns,
                    COALESCE(SUM(amount_inr), 0)::float AS total_volume_inr,
                    COALESCE(SUM(CASE WHEN current_status = 'PENDING' THEN amount_inr ELSE 0 END), 0)::float AS pending_volume_inr,
                    COUNT(*) FILTER (WHERE current_status IN ('FAILED', 'PENDING'))::int AS issue_count
                FROM transaction;
            """)
            kpi = dict(cur.fetchone())
            kpi["issue_rate_pct"] = (
                round((kpi["issue_count"] / kpi["total_txns"]) * 100, 2)
                if kpi["total_txns"] > 0
                else 0.0
            )

            # 2. Payment Rail Health (Stacked Bar Chart)
            cur.execute("""
                SELECT
                    rail,
                    COUNT(*) FILTER (WHERE current_status = 'SUCCESS')::int AS success,
                    COUNT(*) FILTER (WHERE current_status = 'PENDING')::int AS pending,
                    COUNT(*) FILTER (WHERE current_status = 'FAILED')::int AS failed,
                    COALESCE(SUM(amount_inr), 0)::float AS total_volume_inr
                FROM transaction
                GROUP BY rail
                ORDER BY total_volume_inr DESC;
            """)
            rail_health = [dict(r) for r in cur.fetchall()]

            # 3. Failure & Pending Root Causes (Donut Chart)
            cur.execute("""
                SELECT
                    COALESCE(response_code, 'UNKNOWN') AS reason,
                    COUNT(*)::int AS count
                FROM txn_event
                WHERE response_code IS NOT NULL AND response_code <> ''
                GROUP BY response_code
                ORDER BY count DESC
                LIMIT 6;
            """)
            root_causes = [dict(r) for r in cur.fetchall()]

            # 4. Approval Queue Breakdown (Horizontal Bar Chart)
            cur.execute("""
                SELECT
                    action_type,
                    status,
                    COUNT(*)::int AS count
                FROM approval_request
                GROUP BY action_type, status
                ORDER BY count DESC;
            """)
            approvals = [dict(r) for r in cur.fetchall()]

        conn.rollback()
        return {
            "kpis": kpi,
            "rail_health": rail_health,
            "root_causes": root_causes,
            "approvals": approvals,
        }
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Metrics query failed: {str(e)}")
    finally:
        conn.close()