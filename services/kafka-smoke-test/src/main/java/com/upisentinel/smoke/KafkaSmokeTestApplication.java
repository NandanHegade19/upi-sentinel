package com.upisentinel.smoke;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.CommandLineRunner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.SendResult;

import java.time.Instant;
import java.util.concurrent.TimeUnit;

@SpringBootApplication
public class KafkaSmokeTestApplication {

    private static final Logger log = LoggerFactory.getLogger(KafkaSmokeTestApplication.class);
    private static final String TOPIC = "txn.events";

    public static void main(String[] args) {
        SpringApplication.run(KafkaSmokeTestApplication.class, args);
    }

    @Bean
    CommandLineRunner publishOneMessage(KafkaTemplate<String, String> kafka) {
        return args -> {
            // The transaction ID is the key, so all events of one transaction stay ordered
            String key = "TXN-SMOKE-0001";
            String value = """
                    {"txnId":"%s","rail":"UPI","status":"INITIATED","amountInr":4999.00,"eventTime":"%s"}
                    """.formatted(key, Instant.now()).trim();

            // get() blocks until the broker acknowledges, so errors surface here
            SendResult<String, String> result = kafka.send(TOPIC, key, value).get(10, TimeUnit.SECONDS);

            log.info("Published to topic={} partition={} offset={}",
                    result.getRecordMetadata().topic(),
                    result.getRecordMetadata().partition(),
                    result.getRecordMetadata().offset());
        };
    }
}