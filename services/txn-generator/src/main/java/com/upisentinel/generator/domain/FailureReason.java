package com.upisentinel.generator.domain;

/**
 * Internal, human-readable reasons. These are NOT official NPCI/RBI response codes.
 * In Week 2 we map them to the real codes found in the public documents.
 */
public enum FailureReason {
    INSUFFICIENT_FUNDS, WRONG_PIN, DAILY_LIMIT_EXCEEDED, ACCOUNT_BLOCKED,
    BENEFICIARY_BANK_DOWN, ISSUER_TIMEOUT, NETWORK_TIMEOUT, DEBIT_NOT_CREDITED
}
