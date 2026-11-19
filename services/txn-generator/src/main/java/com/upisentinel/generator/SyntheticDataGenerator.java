package com.upisentinel.generator;

import com.upisentinel.generator.domain.Customer;
import com.upisentinel.generator.domain.FailureReason;
import com.upisentinel.generator.domain.PaymentTransaction;
import com.upisentinel.generator.domain.Rail;
import com.upisentinel.generator.domain.TxnStatus;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Random;
import java.util.Set;
import java.util.UUID;

/**
 * Creates synthetic customers and transactions.
 *
 * Determinism rule: ALL randomness comes from one seeded Random, and no clock is read.
 * Same seed + same settings => byte-for-byte identical output.
 * Keep it that way: never call Instant.now(), UUID.randomUUID() or Math.random() in here.
 *
 * Amount ranges are simplified assumptions for realistic-looking data. Verify real rail limits
 * against NPCI/RBI documents before relying on them in any business rule.
 */
public class SyntheticDataGenerator {

    private static final String[] FIRST_NAMES = {
            "Aarav", "Priya", "Rohan", "Ananya", "Vikram", "Meera", "Karthik", "Divya", "Arjun", "Kavya",
            "Suresh", "Lakshmi", "Imran", "Fatima", "Harpreet", "Neha", "Sanjay", "Pooja", "Rahul", "Asha"};
    private static final String[] LAST_NAMES = {
            "Sharma", "Hegde", "Patil", "Nair", "Reddy", "Iyer", "Khan", "Singh", "Gowda", "Kulkarni",
            "Joshi", "Menon", "Das", "Shetty", "Verma", "Rao", "Bhat", "Naik", "Gupta", "Pillai"};
    private static final String[] VPA_HANDLES = {"okaxis", "oksbi", "okhdfcbank", "ybl", "paytm", "ibl"};

    // Share of traffic per rail (percent)
    private static final Rail[] RAILS = {Rail.UPI, Rail.IMPS, Rail.NEFT, Rail.RTGS, Rail.MANDATE};
    private static final int[] RAIL_WEIGHTS = {80, 8, 6, 1, 5};

    // Non-success outcomes (percent of the "failure rate" share)
    private static final TxnStatus[] PROBLEM_STATUSES = {
            TxnStatus.FAILED, TxnStatus.PENDING, TxnStatus.REVERSED, TxnStatus.DEEMED_SUCCESS};
    private static final int[] PROBLEM_WEIGHTS = {50, 25, 15, 10};

    private static final FailureReason[] FAILED_REASONS = {
            FailureReason.INSUFFICIENT_FUNDS, FailureReason.WRONG_PIN, FailureReason.DAILY_LIMIT_EXCEEDED,
            FailureReason.ACCOUNT_BLOCKED, FailureReason.BENEFICIARY_BANK_DOWN, FailureReason.ISSUER_TIMEOUT};
    private static final FailureReason[] PENDING_REASONS = {
            FailureReason.ISSUER_TIMEOUT, FailureReason.BENEFICIARY_BANK_DOWN, FailureReason.NETWORK_TIMEOUT};
    private static final FailureReason[] REVERSED_REASONS = {
            FailureReason.DEBIT_NOT_CREDITED, FailureReason.BENEFICIARY_BANK_DOWN};

    // Fixed mandate amounts: subscriptions, EMIs, SIPs
    private static final int[] MANDATE_AMOUNTS = {99, 199, 499, 999, 1500, 2500, 5000, 10000};

    private final GeneratorProperties settings;
    private final Random random;

    public SyntheticDataGenerator(GeneratorProperties settings) {
        this.settings = settings;
        this.random = new Random(settings.seed());
    }

    public List<Customer> generateCustomers() {
        List<Customer> customers = new ArrayList<>(settings.customers());
        for (int i = 0; i < settings.customers(); i++) {
            String first = pick(FIRST_NAMES);
            String last = pick(LAST_NAMES);
            String vpa = maskedVpa(first) + "@" + pick(VPA_HANDLES);
            // Created 30 to 730 days before the simulation starts
            Instant createdAt = settings.startTime().minusSeconds(86_400L * (30 + random.nextInt(700)));
            customers.add(new Customer(nextUuid(), first + " " + last.charAt(0) + ".", vpa, createdAt));
        }
        return customers;
    }

    public List<PaymentTransaction> generateTransactions(List<Customer> customers) {
        if (customers.size() < 2) throw new IllegalArgumentException("need at least 2 customers");

        List<PaymentTransaction> result = new ArrayList<>(settings.transactions());
        Set<String> usedIds = new HashSet<>();
        long spanSeconds = settings.spanHours() * 3600L;

        for (int i = 0; i < settings.transactions(); i++) {
            Rail rail = weighted(RAILS, RAIL_WEIGHTS);
            Customer payer = customers.get(random.nextInt(customers.size()));
            Customer payee;
            do {
                payee = customers.get(random.nextInt(customers.size()));
            } while (payee.customerId().equals(payer.customerId()));

            TxnStatus status = TxnStatus.SUCCESS;
            FailureReason reason = null;
            if (random.nextDouble() < settings.failureRate()) {
                status = weighted(PROBLEM_STATUSES, PROBLEM_WEIGHTS);
                reason = reasonFor(status);
            }

            Instant createdAt = settings.startTime().plusSeconds((long) (random.nextDouble() * spanSeconds));
            result.add(new PaymentTransaction(
                    uniqueTxnId(rail, usedIds), rail, amountFor(rail), payer.customerId(), payee.customerId(),
                    status, reason, createdAt));
        }
        result.sort(Comparator.comparing(PaymentTransaction::createdAt).thenComparing(PaymentTransaction::txnId));
        return result;
    }

    // ---- helpers ------------------------------------------------------------------------------

    private BigDecimal amountFor(Rail rail) {
        double value = switch (rail) {
            case UPI -> logNormal(450, 1.3, 1, 100_000);
            case IMPS -> logNormal(5_000, 1.1, 100, 500_000);
            case NEFT -> logNormal(25_000, 1.3, 500, 2_500_000);
            case RTGS -> 200_000 + random.nextDouble() * 4_800_000; // RTGS has a high minimum
            case MANDATE -> MANDATE_AMOUNTS[random.nextInt(MANDATE_AMOUNTS.length)];
        };
        return BigDecimal.valueOf(value).setScale(2, RoundingMode.HALF_UP);
    }

    /** Many small payments, a few large ones: realistic for money movement. */
    private double logNormal(double median, double sigma, double min, double max) {
        double v = median * Math.exp(sigma * random.nextGaussian());
        return Math.min(max, Math.max(min, v));
    }

    private FailureReason reasonFor(TxnStatus status) {
        return switch (status) {
            case FAILED -> pick(FAILED_REASONS);
            case PENDING -> pick(PENDING_REASONS);
            case REVERSED -> pick(REVERSED_REASONS);
            case DEEMED_SUCCESS -> FailureReason.NETWORK_TIMEOUT;
            case SUCCESS -> null;
        };
    }

    private String uniqueTxnId(Rail rail, Set<String> used) {
        String id;
        do {
            id = rail.idPrefix() + String.format("%012d", Math.floorMod(random.nextLong(), 1_000_000_000_000L));
        } while (!used.add(id));
        return id;
    }

    private String maskedVpa(String firstName) {
        return firstName.substring(0, 2).toLowerCase() + "****";
    }

    private UUID nextUuid() {
        return new UUID(random.nextLong(), random.nextLong());
    }

    private <T> T pick(T[] values) {
        return values[random.nextInt(values.length)];
    }

    private <T> T weighted(T[] values, int[] weights) {
        int total = 0;
        for (int w : weights) total += w;
        int roll = random.nextInt(total);
        for (int i = 0; i < values.length; i++) {
            roll -= weights[i];
            if (roll < 0) return values[i];
        }
        return values[values.length - 1];
    }
}
