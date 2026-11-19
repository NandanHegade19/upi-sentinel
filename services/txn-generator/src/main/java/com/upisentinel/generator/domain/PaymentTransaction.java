package com.upisentinel.generator.domain;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

/** One synthetic payment. failureReason is null when the status is SUCCESS. */
public record PaymentTransaction(
        String txnId,
        Rail rail,
        BigDecimal amountInr,
        UUID payerId,
        UUID payeeId,
        TxnStatus currentStatus,
        FailureReason failureReason,
        Instant createdAt) {
}
