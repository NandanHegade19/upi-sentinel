package com.upisentinel.generator;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.time.Instant;

/** Settings from application.yml (prefix "generator"). Validated up front so bad config fails fast. */
@ConfigurationProperties(prefix = "generator")
public record GeneratorProperties(
        long seed,
        int customers,
        int transactions,
        double failureRate,
        Instant startTime,
        int spanHours,
        int scenariosPerType,
        String outputDir) {

    public GeneratorProperties {
        if (customers < 2) throw new IllegalArgumentException("customers must be at least 2");
        if (transactions < 1) throw new IllegalArgumentException("transactions must be at least 1");
        if (failureRate < 0.0 || failureRate > 1.0) throw new IllegalArgumentException("failureRate must be between 0 and 1");
        if (spanHours < 1) throw new IllegalArgumentException("spanHours must be at least 1");
        if (scenariosPerType < 0) throw new IllegalArgumentException("scenariosPerType must not be negative");
        if (startTime == null) throw new IllegalArgumentException("startTime is required");
    }
}
