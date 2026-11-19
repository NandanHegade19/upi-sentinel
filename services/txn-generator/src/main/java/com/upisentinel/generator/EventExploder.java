package com.upisentinel.generator;

import com.upisentinel.generator.domain.PaymentTransaction;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

public class EventExploder{

    public static List<TxnEventPayload> explode(PaymentTransaction txn) {
        List<TxnEventPayload> events = new ArrayList<>();
        Instant baseTime = txn.createdAt();

        switch (txn.currentStatus()){
            case SUCCESS -> {
                events.add(createEvent(txn, "DEBITED", null, baseTime.plusSeconds(1)));
                events.add(createEvent(txn, "SUCCESS", null, baseTime.plusSeconds(2)));
            }
            case FAILED -> {
                // E.g., INSUFFICIENT_FUNDS, DAILY_LIMIT_EXCEEDED (No debit occurs)
                events.add(createEvent(txn, "FAILED", getReasonCode(txn), baseTime.plusSeconds(1)));
            }
            case PENDING -> {
                events.add(createEvent(txn, "DEBITED", null, baseTime.plusSeconds(1)));
                events.add(createEvent(txn, "PENDING", getReasonCode(txn), baseTime.plusSeconds(2)));
            }
            case REVERSED -> {
                events.add(createEvent(txn, "DEBITED", null, baseTime.plusSeconds(1)));
                events.add(createEvent(txn, "PENDING", getReasonCode(txn), baseTime.plusSeconds(2)));
                events.add(createEvent(txn, "REVERSED", getReasonCode(txn), baseTime.plusSeconds(120)));
            }
            case DEEMED_SUCCESS -> {
                events.add(createEvent(txn, "DEBITED", null, baseTime.plusSeconds(1)));
                events.add(createEvent(txn, "DEEMED_SUCCESS", getReasonCode(txn), baseTime.plusSeconds(2)));
            }
        }
        return events;
    }

    private static TxnEventPayload createEvent(PaymentTransaction txn, String status, String reasonCode, Instant time){
        // Deterministic UUID based on txnId + status ensures idempotency on replay
        UUID eventId = UUID.nameUUIDFromBytes((txn.txnId() + "-" + status).getBytes());
        return new TxnEventPayload(
                eventId,
                txn.txnId(),
                txn.rail().name(),
                txn.amountInr(),
                txn.payerId(),
                txn.payeeId(),
                status,
                reasonCode,
                "TXN_CORE",
                time
        );
    }

    private static String getReasonCode(PaymentTransaction txn){
        return txn.failureReason() != null ? txn.failureReason().name() : null;
    }

}