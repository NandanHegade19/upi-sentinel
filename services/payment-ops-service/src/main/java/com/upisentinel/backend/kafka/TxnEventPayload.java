package com.upisentinel.backend.kafka;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

public record TxnEventPayload (
        UUID eventId,
        String txnId,
        String rail,
        BigDecimal amountInr,
        UUID payeeId,
        UUID payerId,
        String status,
        String responseCode,
        String sourceSystem,
        Instant eventTime
){}
