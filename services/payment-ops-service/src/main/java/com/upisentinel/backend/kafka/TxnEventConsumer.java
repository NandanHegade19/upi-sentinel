package com.upisentinel.backend.kafka;

import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Service;

@Service
public class TxnEventConsumer {

    private static final Logger log = LoggerFactory.getLogger(TxnEventConsumer.class);

    private final TxnEventRepository txnEventRepository;
    private final TransactionRepository transactionRepository;

    // Constructor injection for dependencies
    public TxnEventConsumer(TxnEventRepository txnEventRepository,
                            TransactionRepository transactionRepository) {
        this.txnEventRepository = txnEventRepository;
        this.transactionRepository = transactionRepository;
    }

    @KafkaListener(topics = "txn.events", groupId = "txn-pipeline-group")
    public void consumeEvent(ConsumerRecord<String, TxnEventPayload> record) {
        TxnEventPayload event = record.value();

        // 1. Upsert parent transaction table using state priority logic
        transactionRepository.upsertWithStatePriority(event);

        // 2. Insert into append-only log (ignores duplicates via DB constraint)
        boolean isNewEvent = txnEventRepository.saveIdempotent(event);
        log.debug("Consumed event for txn: {} with status: {}", event.txnId(), event.status());

        if (!isNewEvent) {
            log.debug("Duplicate event ignored for txn: {}", event.txnId());
        }
    }
}