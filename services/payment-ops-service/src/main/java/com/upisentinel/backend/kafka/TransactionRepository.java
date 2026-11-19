package com.upisentinel.backend.kafka;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

@Repository
public class TransactionRepository {

    private final JdbcTemplate jdbc;

    public TransactionRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public void upsertWithStatePriority(TxnEventPayload event) {
        // Solves out-of-order events: a late PENDING cannot overwrite a SUCCESS.
        // Status weights: INITIATED(1) -> DEBITED(2) -> PENDING(3) -> TERMINAL STATES(4)
        String sql = """
            INSERT INTO transaction (txn_id, rail, amount_inr, payer_id, payee_id, current_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (txn_id) DO UPDATE SET
                current_status = EXCLUDED.current_status
            WHERE
                CASE transaction.current_status
                    WHEN 'INITIATED' THEN 1
                    WHEN 'DEBITED' THEN 2
                    WHEN 'PENDING' THEN 3
                    ELSE 4
                END
                <=
                CASE EXCLUDED.current_status
                    WHEN 'INITIATED' THEN 1
                    WHEN 'DEBITED' THEN 2
                    WHEN 'PENDING' THEN 3
                    ELSE 4
                END
            """;

        jdbc.update(sql,
                event.txnId(),
                event.rail(),
                event.amountInr(),
                event.payerId(),
                event.payeeId(),
                event.status(),
                java.sql.Timestamp.from(event.eventTime()));
    }
}
