package com.upisentinel.generator;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;

import java.util.List;

@Component
public class KafkaEventPublisher {

    private static final Logger log = LoggerFactory.getLogger(KafkaEventPublisher.class);
    private static final String TOPIC = "txn.events";

    private final KafkaTemplate<String, TxnEventPayload> kafkaTemplate;

    public KafkaEventPublisher(KafkaTemplate<String, TxnEventPayload> kafkaTemplate){
        this.kafkaTemplate = kafkaTemplate;
    }

    public void publishTimeline(List<TxnEventPayload> timeline){
        for(TxnEventPayload event : timeline){
            kafkaTemplate.send(TOPIC, event.txnId(), event);
        }
        log.debug("Published {} events for txn: {}", timeline.size(), timeline.get(0).txnId());
    }
}
