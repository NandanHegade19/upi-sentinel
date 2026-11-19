import os
import psycopg
from pgvector.psycopg import register_vector
from src.models.schemas import SearchRequest, SearchResult
import json
from datetime import datetime

DB_CONN = os.getenv("DB_CONN", "postgresql://sentinel:sentinel_dev@localhost:5432/sentinel")

def search_knowledge(req: SearchRequest, embedder) -> list[SearchResult]:
    query_embedding = embedder.encode(req.query).tolist()
    results = []
    MIN_SIMILARITY = 0.38 # Tunable threshold
    with psycopg.connect(DB_CONN) as conn:
        register_vector(conn)
        with conn.cursor() as cur:
            cur.execute("""
            SELECT document_name, page_number, text, 
                       1 - (embedding <=> %s::vector) AS similarity_score
                FROM knowledge_chunk
                ORDER BY embedding <=> %s::vector ASC
                LIMIT %s
            """, (query_embedding, query_embedding, req.top_k))

            for row in cur.fetchall():
                # Only append if it meets the minimum threshold
                if row[3] >= MIN_SIMILARITY:
                    results.append(SearchResult(
                        document_name = row[0],
                        page_number = row[1],
                        text = row[2],
                        similarity_score = row[3]
                    ))
    #print(f"results ------->> {results}")
    return results

def update_fraud_feedback(flag_id: int, feedback: str) -> dict:
    """Updates the analyst feedback for a specific fraud flag."""
    with psycopg.connect(DB_CONN) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE fraud_flag
                SET analyst_feedback = %s
                WHERE flag_id = %s
                RETURNING flag_id;
            """, (feedback, flag_id))
            updated_row = cur.fetchone()
            conn.commit()
            
            if not updated_row:
                return {"error": f"Fraud flag ID {flag_id} not found."}
                
            return {
                "status": "success", 
                "message": f"Flag {flag_id} marked as {feedback}."
            }

def get_mule_id_from_txn(txn_id: str) -> str:
    """Finds the user UUID associated with a given transaction ID."""
    with psycopg.connect(DB_CONN) as conn:
        with conn.cursor() as cur:
            # Get the payer_id (UUID) for this specific transaction
            cur.execute("SELECT payer_id FROM transaction WHERE txn_id = %s", (txn_id,))
            result = cur.fetchone()
            if not result:
                raise ValueError(f"Transaction {txn_id} not found")
            return str(result[0])

def get_mule_network(mule_id: str) -> dict:
    """US 4.4 Fetches the inbound and outbound transaction network of suspected mule"""
    edges = []
    with psycopg.connect(DB_CONN) as conn:
        with conn.cursor() as cur:
            # Get Inbound (Fan-in) and Outbound (Fan-out) flows
            cur.execute("""
                Select payer_id, payee_id, amount_inr, created_at, 'INBOUND' as direction
                FROM transaction
                WHERE payee_id = %s

                UNION ALL

                SELECT payer_id, payee_id, amount_inr, created_at, 'OUTBOUND' as direction 
                FROM transaction
                WHERE payer_id = %s

                ORDER BY created_at ASC;
            """, (mule_id, mule_id))

            for row in cur.fetchall():
                edges.append({
                    "source_id": str(row[0]),
                    "target_id": str(row[1]),
                    "amount": float(row[2]),
                    "timestamp": str(row[3]),
                    "direction": row[4],
                })
    return {"mule_id": mule_id, "edges": edges}

def log_audit_event(user_role: str, action_type: str, details: dict, txn_id: str = None) -> None:
    """US-5.4: Immutable audit trail for all agent interactions."""
    try:
        with psycopg.connect(DB_CONN) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT into audit_log (user_role, action_type, txn_id, details)
                    VALUES (%s, %s, %s, %s)
                    """, (user_role, action_type, txn_id, json.dumps(details)))
                conn.commit()
    except Exception as ex:
        print(f"[AUDIT LOG FAILED] Critical compliance error: {ex}")

def process_dpdp_deletion(customer_id: str) -> dict:
    """US-5.5: Right to be forgotten. Anonymizes ledger history."""
    try:
        with psycopg.connect(DB_CONN) as conn:
            with conn.cursor() as cur:
                # 1. Anonymize ledger (Financial compliance - keep the row, scrub the human)
                cur.execute("""
                    UPDATE transaction 
                    SET payer_id = '00000000-0000-0000-0000-000000000000' 
                    WHERE payer_id = %s
                """, (customer_id,))
                payer_rows = cur.rowcount
                
                cur.execute("""
                    UPDATE transaction 
                    SET payee_id = '00000000-0000-0000-0000-000000000000' 
                    WHERE payee_id = %s
                """, (customer_id,))
                payee_rows = cur.rowcount
                
                total_anonymized = payer_rows + payee_rows
                
                # 2. Immutable proof of deletion
                cur.execute("""
                    INSERT INTO audit_log (user_role, action_type, details)
                    VALUES ('compliance_system', 'DPDP_DELETION', %s)
                """, (json.dumps({"target_customer": customer_id, "transactions_anonymized": total_anonymized}),))
                
                conn.commit()
                
                if total_anonymized == 0:
                    return {"status": "success", "message": f"No records found for customer {customer_id}."}
                    
                return {"status": "success", "message": f"Customer {customer_id} successfully anonymized across {total_anonymized} transactions."}
    except Exception as e:
        return {"error": str(e)}

def get_live_alerts(limit: int = 10, offset: int = 0) -> list[dict]:
    """Fetches pending fraud alerts for the Live Queue with pagination."""
    alerts = []
    with psycopg.connect(DB_CONN) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT t.txn_id, t.amount_inr, f.anomaly_score, t.created_at
                FROM transaction t
                JOIN fraud_flag f ON t.txn_id = f.txn_id
                WHERE f.analyst_feedback = 'PENDING'
                ORDER BY t.created_at DESC
                LIMIT %s OFFSET %s;
            """, (limit, offset))
            
            for row in cur.fetchall():
                alerts.append({
                    "id": str(row[0]),
                    "amount": float(row[1]),
                    "score": float(row[2]) if row[2] is not None else 0, # Displays the anomaly_score (e.g., -1)
                    "time": row[3].strftime("%H:%M:%S") if hasattr(row[3], 'strftime') else str(row[3]).split(' ')[1][:8]
                })
    return alerts

def propose_action(txn_id: str, action_type: str, reason: str) -> dict:
    """Submits a write action (REFUND/REVERSAL/DISPUTE) into the approval queue."""
    try:
        with psycopg.connect(DB_CONN) as conn:
            with conn.cursor() as cur:
                run_id = str(uuid.uuid4())
                payload_json = json.dumps({
                    "txn_id": txn_id,
                    "reason": reason
                })
                
                cur.execute("""
                    INSERT INTO approval_request (run_id, action_type, payload, status)
                    VALUES (%s, %s, %s, 'PENDING')
                    RETURNING request_id;
                """, (run_id, action_type, payload_json))
                
                conn.commit()
                
                return {
                    "status": "success", 
                    "message": f"{action_type} for {txn_id} has been successfully submitted to the approval queue."
                }
    except Exception as e:
        print(f"=== DB ERROR IN PROPOSE_ACTION: {str(e)} ===")
        return {"error": f"Database error: {str(e)}"}

def get_approval_requests(status: str = None, txn_id: str = None, date_filter: str = None) -> list[dict]:
    """Fetches approval queue or history, with optional filtering."""
    results = []
    with psycopg.connect(DB_CONN) as conn:
        with conn.cursor() as cur:
            query = """
                SELECT request_id, run_id, action_type, payload, status, 
                       decided_by, decision_reason, decided_at
                FROM approval_request
                WHERE 1=1
            """
            params = []
            
            if status:
                query += " AND status = %s"
                params.append(status)
            if txn_id:
                # Use JSON extraction to search inside the payload column
                query += " AND payload->>'txn_id' = %s"
                params.append(txn_id)
            if date_filter:
                query += " AND (DATE(decided_at) = %s OR decided_at IS NULL)"
                params.append(date_filter)
                
            query += " ORDER BY request_id DESC LIMIT 50;"
            
            cur.execute(query, params)
            
            for row in cur.fetchall():
                results.append({
                    "request_id": row[0],
                    "run_id": row[1],
                    "action_type": row[2],
                    "payload": row[3] if isinstance(row[3], dict) else json.loads(row[3]),
                    "status": row[4],
                    "decided_by": row[5],
                    "decision_reason": row[6],
                    "decided_at": str(row[7]) if row[7] else None
                })
    return results

def get_audit_logs(txn_id: str = None, date_filter: str = None) -> list[dict]:
    """Fetches the immutable audit trail with optional filtering."""
    results = []
    with psycopg.connect(DB_CONN) as conn:
        with conn.cursor() as cur:
            query = """
                SELECT user_role, action_type, txn_id, details, created_at
                FROM audit_log
                WHERE 1=1
            """
            params = []
            
            if txn_id:
                query += " AND txn_id = %s"
                params.append(txn_id)
            if date_filter:
                query += " AND DATE(created_at) = %s"
                params.append(date_filter)
                
            query += " ORDER BY created_at DESC LIMIT 50;"
            
            cur.execute(query, params)
            
            for row in cur.fetchall():
                results.append({
                    "user_role": row[0],
                    "action_type": row[1],
                    "txn_id": row[2],
                    "details": row[3] if isinstance(row[3], dict) else json.loads(row[3]),
                    "created_at": str(row[4])
                })
    return results

def resolve_approval_request(request_id: int, decision: str, decided_by: str, reason: str = "") -> dict:
    """Marks a pending request as APPROVED or REJECTED and logs the audit trail."""
    try:
        with psycopg.connect(DB_CONN) as conn:
            with conn.cursor() as cur:
                # 1. Update the approval request
                cur.execute("""
                    UPDATE approval_request
                    SET status = %s, decided_by = %s, decision_reason = %s, decided_at = CURRENT_TIMESTAMP
                    WHERE request_id = %s AND status = 'PENDING'
                    RETURNING request_id, payload->>'txn_id', action_type;
                """, (decision, decided_by, reason, request_id))
                
                row = cur.fetchone()
                if not row:
                    return {"error": f"Request #{request_id} not found or is no longer PENDING."}
                
                req_id, txn_id, action_type = row
                
                # 2. Log the immutable audit event
                audit_details = {
                    "request_id": req_id,
                    "original_action": action_type,
                    "decision": decision,
                    "decision_reason": reason
                }
                cur.execute("""
                    INSERT INTO audit_log (user_role, action_type, txn_id, details)
                    VALUES (%s, %s, %s, %s)
                """, (decided_by, f"DECISION_{decision}", txn_id, json.dumps(audit_details)))
                
                conn.commit()
                return {"status": "success", "message": f"Request #{request_id} has been {decision}."}
    except Exception as e:
        print(f"=== DB ERROR IN RESOLVE_APPROVAL: {str(e)} ===")
        return {"error": f"Database error: {str(e)}"}