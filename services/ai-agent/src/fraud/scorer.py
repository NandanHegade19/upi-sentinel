import os
import json
import psycopg
import pandas as pd
from kafka import KafkaConsumer
from sklearn.ensemble import IsolationForest
from groq import Groq
from dotenv import load_dotenv


load_dotenv()

DB_CONN = os.getenv("DB_CONN", "postgresql://sentinel:sentinel_dev@localhost:5432/sentinel")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# Pre-fit an Isolation Forest with our expected normal/abnormal baselines
# In a real system, this is trained on historical DB data (US-4.3 Retraining)
baseline_data = pd.DataFrame([
    {'fan_in': 1, 'fwd_ratio': 0.0},     # Normal peer-to-peer
    {'fan_in': 2, 'fwd_ratio': 0.1},     # Normal peer-to-peer
    {'fan_in': 45, 'fwd_ratio': 0.05},   # TRAP: Busy Merchant (High fan-in, keeps money)
    {'fan_in': 32, 'fwd_ratio': 0.97},   # MULE: High fan-in, immediate high fan-out
])

model = IsolationForest(random_state = 42, contamination = 0.25)
model.fit(baseline_data[['fan_in', 'fwd_ratio']])

def generate_explanation(fan_in: int, fwd_ratio: float) -> str:
    """US-4.2: Strict plain-English explanation using only computed facts."""

    pct = int(fwd_ratio*100)
    prompt = f""" You are a banking fraud analyst AI.
    Write exactly in ONE sentence explaining why this account is flagged as a mule.
    You MUST use these exact numbers: {fan_in} unique senders, and {pct}% of the money forwarded
    Do not invent any other facts, names, or timelines.
    """

    res = groq_client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0
    )
    return res.choices[0].message.content.strip()

def get_account_features(payee_id: str, event_time: str):
    """Query the DB for the payee's 2-hour fan-in and 24-hour fan-out velocity based on the event's timestamp."""
    with psycopg.connect(DB_CONN) as conn:
        with conn.cursor() as cur:
            # Fan-in: Unique senders to this payee in the 2 hours before this event
            cur.execute("""
                SELECT COUNT(DISTINCT payer_id), COALESCE(SUM(amount_inr), 0)
                FROM transaction
                WHERE payee_id = %s 
                AND created_at <= %s::timestamp 
                AND created_at >= %s::timestamp - INTERVAL '2 hours'
            """, (payee_id, event_time, event_time))
            fan_in, total_received = cur.fetchone()

            if total_received == 0:
                return fan_in, 0.0

            # Fan-out: Money forwarded by this payee in the 24 hours before this event
            cur.execute("""
                SELECT COALESCE(SUM(amount_inr), 0)
                FROM transaction
                WHERE payer_id = %s 
                AND created_at <= %s::timestamp
                AND created_at >= %s::timestamp - INTERVAL '24 hours'
            """, (payee_id, event_time, event_time))
            total_forwarded = cur.fetchone()[0]
            
            fwd_ratio = min(float(total_forwarded) / float(total_received), 1.0)
            return fan_in, fwd_ratio

def process_stream():
    print("Starting Fraud ML Scorer on 'txn.events' topic...")
    consumer = KafkaConsumer(
        'txn.events',
        bootstrap_servers=['localhost:9092'],
        auto_offset_reset='earliest',
        value_deserializer=lambda m: json.loads(m.decode('utf-8'))
    )

    from datetime import datetime, timezone

    # Track payees we have already flagged to prevent alert spam
    flagged_payees = set()

    for message in consumer:
        event = message.value
        
        if event.get('status') == 'SUCCESS':
            payee_id = event.get('payeeId')
            txn_id = event.get('txnId')

            # Skip if we already flagged this payee
            if payee_id in flagged_payees:
                continue
            
            # Catch the Java epoch float and convert it to an ISO-8601 string
            event_time_raw = event.get('eventTime')
            if isinstance(event_time_raw, (int, float)):
                event_time = datetime.fromtimestamp(event_time_raw, tz=timezone.utc).isoformat()
            else:
                event_time = str(event_time_raw)
            
            # 1. Feature Engineering
            fan_in, fwd_ratio = get_account_features(payee_id, event_time)
            
            if fan_in > 5:
                # 2. ML Scoring (US-4.1)
                df = pd.DataFrame([{'fan_in': fan_in, 'fwd_ratio': fwd_ratio}])
                anomaly_score = model.predict(df[['fan_in', 'fwd_ratio']])[0]
                
                # -1 indicates Anomaly (Fraud)
                if anomaly_score == -1:
                    print(f"FRAUD DETECTED [Txn: {txn_id} | Payee: {payee_id}] - Fan-In: {fan_in}, Fwd: {fwd_ratio:.2f}")

                    # NEW: Add to our tracking set
                    flagged_payees.add(payee_id)
                    
                    # 3. LLM Explanation (US-4.2)
                    explanation = generate_explanation(fan_in, fwd_ratio)
                    
                    # 4. Save to Ranked Queue
                    with psycopg.connect(DB_CONN) as conn:
                        with conn.cursor() as cur:
                            cur.execute("""
                                INSERT INTO fraud_flag (txn_id, payee_id, fan_in_count, forwarding_ratio, anomaly_score, llm_explanation)
                                VALUES (%s, %s, %s, %s, %s, %s)
                            """, (txn_id, payee_id, fan_in, fwd_ratio, float(anomaly_score), explanation))
                            conn.commit()

if __name__ == "__main__":
    process_stream()