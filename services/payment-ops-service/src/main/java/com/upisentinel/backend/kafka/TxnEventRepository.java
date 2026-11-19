package com.upisentinel.backend.kafka;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

@Repository
public class TxnEventRepository {

    private final JdbcTemplate jdbc;

    public TxnEventRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public boolean saveIdempotent(TxnEventPayload event){
        String sql = """
                Insert into txn_event (event_id, txn_id, status, response_code, source_system, event_time)
                VALUES (?,?,?,?,?,?)
                ON CONFLICT (event_id) DO NOTHING
                """;

        int rowsAffected = jdbc.update(sql,
                event.eventId(),
                event.txnId(),
                event.status(),
                event.responseCode(),
                event.sourceSystem(),
                java.sql.Timestamp.from(event.eventTime()));

        return rowsAffected > 0;
    }
}
