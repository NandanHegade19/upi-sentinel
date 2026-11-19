package com.upisentinel.generator;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.upisentinel.generator.domain.Customer;
import com.upisentinel.generator.domain.PaymentTransaction;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;

import java.io.BufferedWriter;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/** Generates the data and writes it as JSON Lines (one JSON object per line). */
@Component
public class GeneratorRunner implements CommandLineRunner {

    private static final Logger log = LoggerFactory.getLogger(GeneratorRunner.class);

    private final GeneratorProperties settings;
    private final ObjectMapper mapper;
    private final KafkaEventPublisher kafkaPublisher;

    public GeneratorRunner(GeneratorProperties settings, ObjectMapper mapper, KafkaEventPublisher kafkaPublisher) {
        this.settings = settings;
        this.mapper = mapper;
        this.kafkaPublisher = kafkaPublisher;
    }

    @Override
    public void run(String... args) throws Exception {
        SyntheticDataGenerator generator = new SyntheticDataGenerator(settings);
        List<Customer> customers = generator.generateCustomers();
        List<PaymentTransaction> baseTransactions = generator.generateTransactions(customers);

        ScenarioInjector.Result scenarios = new ScenarioInjector(settings).inject(customers, baseTransactions);
        List<PaymentTransaction> transactions = new ArrayList<>(baseTransactions);
        transactions.addAll(scenarios.transactions());
        transactions.sort(Comparator.comparing(PaymentTransaction::createdAt).thenComparing(PaymentTransaction::txnId));

        // 1. Write the static reference files needed for the Epic 7 Evaluation script
        Path dir = Path.of(settings.outputDir());
        Files.createDirectories(dir);
        writeLines(dir.resolve("customers.jsonl"), customers);
        writeLines(dir.resolve("transactions.jsonl"), transactions);
        writeLines(dir.resolve("scenario-cases.jsonl"), scenarios.cases());

        log.info("seed={} customers={} transactions={} -> {}", settings.seed(), customers.size(),
                transactions.size(), dir.toAbsolutePath());
        log.info("Starting Kafka event stream to topic 'txn.events'...");

        // 2. Explode the static end-states into chronological events and stream them
        int eventCount = 0;
        for(PaymentTransaction txn : transactions){
            List<TxnEventPayload> timeline = EventExploder.explode(txn);
            kafkaPublisher.publishTimeline(timeline);
            eventCount += timeline.size();
        }
        log.info("Streaming complete! Published {} individual state change events.", eventCount);
    }

    private void writeLines(Path file, List<?> items) throws Exception {
        try (BufferedWriter out = Files.newBufferedWriter(file)) {
            for (Object item : items) {
                out.write(mapper.writeValueAsString(item));
                out.newLine();
            }
        }
    }
}
