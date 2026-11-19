import psycopg
import json
import uuid
import re
from datetime import datetime, timedelta
from src.database.queries import DB_CONN
from langfuse import observe


@observe()
def get_transaction_status(txn_id: str) -> dict:
    try:
        with psycopg.connect(DB_CONN) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT txn_id, current_status AS status, amount_inr, rail, created_at, payee_id
                    FROM transaction 
                    WHERE txn_id = %s
                """, (txn_id,))
                row = cur.fetchone()
                
                if not row:
                    return {"error": f"Transaction {txn_id} not found."}
                    
                return {
                    "txn_id": row[0],
                    "status": row[1],
                    "amount": float(row[2]),
                    "rail": row[3],
                    "timestamp": str(row[4]),
                    "payee_id": str(row[5])
                }
    except Exception as e:
        return {"error": str(e)}

@observe()
def propose_action(txn_id: str, action_type: str, reason: str) -> dict:
    try:
        with psycopg.connect(DB_CONN) as conn:
            with conn.cursor() as cur:
                # 1. Hardcoded Guardrail (US-3.7): Prevent refunds on SUCCESS
                if action_type in ("REFUND", "REVERSAL"):
                    cur.execute("SELECT current_status FROM transaction WHERE txn_id = %s", (txn_id,))
                    row = cur.fetchone()
                    if row and row[0] in ("SUCCESS", "DEEMED_SUCCESS"):
                        return {
                            "error": f"Evidence conflicts with requested action. Current status is {row[0]}. Do not propose this action; escalate to L2."
                        }

                # 2. Insert the approval request
                run_id = str(uuid.uuid4())
                payload = json.dumps({"txn_id": txn_id, "reason": reason})
                print(f"Propose resp ===== {run_id} , {payload}, {action_type}")
                cur.execute("""
                    INSERT INTO approval_request (run_id, action_type, payload, current_status)
                    VALUES (%s, %s, %s, 'PENDING')
                    RETURNING request_id;
                """, (run_id, action_type, payload))
                req_id = cur.fetchone()[0]
                conn.commit()
                
        return {
            "status": "success",
            "message": f"Action '{action_type}' for transaction {txn_id} submitted to approval queue.",
            "approval_request_id": req_id
        }
    except Exception as e:
        return {"error": str(e)}

def compute_refund_deadline(transaction_time: str, rule: str) -> dict:
    try:
        clean_time = transaction_time.replace('Z', '+00:00')
        if 'T' not in clean_time and len(clean_time) > 10:
             clean_time = clean_time.replace(' ', 'T')
        
        txn_date = datetime.fromisoformat(clean_time)
        match = re.search(r'T\s*\+\s*(\d+)', rule, re.IGNORECASE)
        if not match:
            return {"error": f"Invalid rule format: {rule}. Expected 'T+1' or 'T+5'."}
            
        days_to_add = int(match.group(1))
        deadline = txn_date + timedelta(days=days_to_add)

        # Dynamic simulated clock: Get the latest event time from the DB
        with psycopg.connect(DB_CONN) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT MAX(event_time) FROM txn_event")
                latest_event = cur.fetchone()[0]
                simulated_now = latest_event if latest_event else datetime.now(txn_date.tzinfo)
        
        return {
            "transaction_time": txn_date.isoformat(),
            "rule_applied": f"T+{days_to_add}",
            "computed_deadline": deadline.isoformat(),
            "simulated_current_time": simulated_now.isoformat(),
            "deadline_passed": simulated_now > deadline
        }
    except Exception as e:
        return {"error": str(e)}

def get_txn_timeline(txn_id: str) -> dict:
    try:
        with psycopg.connect(DB_CONN) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT event_time, status, response_code, source_system 
                    FROM txn_event 
                    WHERE txn_id = %s 
                    ORDER BY event_time ASC
                """, (txn_id,))
                rows = cur.fetchall()
                
                if not rows:
                    return {"error": f"No timeline events found for transaction {txn_id}."}
                
                timeline = [
                    {"event_time": str(row[0]), "status": row[1], "response_code": row[2], "source_system": row[3]}
                    for row in rows
                ]
                return {"txn_id": txn_id, "timeline": timeline}
    except Exception as e:
        return {"error": str(e)}

def lookup_response_code(code: str) -> dict:
    npci_codes = {
        "00": "Approved or completed successfully",
        "U19": "Transaction failed: Payer bank is offline",
        "U30": "Transaction failed: Debit has failed at remitter bank",
        "65": "Transaction failed: Frequency limit exceeded",
        "91": "Transaction failed: Beneficiary bank offline or timeout",
        "U69": "Transaction failed: Timeout at remitter bank"
    }
    return {"response_code": code, "meaning": npci_codes.get(code.upper(), "Unknown response code")}
