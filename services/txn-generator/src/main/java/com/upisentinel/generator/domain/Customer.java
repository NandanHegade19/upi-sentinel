package com.upisentinel.generator.domain;

import java.time.Instant;
import java.util.UUID;

/** Synthetic customer. Only masked identifiers exist, so no real personal data is ever involved. */
public record Customer(UUID customerId, String nameMasked, String vpaMasked, Instant createdAt) {
}
