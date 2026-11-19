package com.upisentinel.generator;

import com.upisentinel.generator.domain.Customer;
import com.upisentinel.generator.domain.FailureReason;
import com.upisentinel.generator.domain.PaymentTransaction;
import com.upisentinel.generator.domain.Rail;
import com.upisentinel.generator.domain.ScenarioCase;
import com.upisentinel.generator.domain.ScenarioType;
import com.upisentinel.generator.domain.TxnStatus;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Random;
import java.util.Set;

/**
 * Adds scripted scenarios on top of the normal traffic.
 *
 * It uses its OWN seeded Random (derived from the main seed). This keeps the US-1.1 data
 * byte-for-byte unchanged whether or not scenarios are switched on, and lets us add or reorder
 * scenarios later without disturbing the base data.
 */
public class ScenarioInjector {

    public record Result(List<PaymentTransaction> transactions, List<ScenarioCase> cases) {}

    private static final long SEED_MIX = 0x5CE7A110L;

    private final GeneratorProperties settings;
    private final Random random;
    private final Set<String> usedIds = new HashSet<>();

    public ScenarioInjector(GeneratorProperties settings) {
        this.settings = settings;
        this.random = new Random(settings.seed() ^ SEED_MIX);
    }

    public Result inject(List<Customer> customers, List<PaymentTransaction> baseTransactions) {
        List<PaymentTransaction> extra = new ArrayList<>();
        List<ScenarioCase> cases = new ArrayList<>();
        if (settings.scenariosPerType() == 0) return new Result(extra, cases);
        if (customers.size() < 10) throw new IllegalArgumentException("scenarios need at least 10 customers");

        baseTransactions.forEach(t -> usedIds.add(t.txnId()));

        for (ScenarioType type : ScenarioType.values()) {
            for (int i = 1; i <= settings.scenariosPerType(); i++) {
                List<PaymentTransaction> txns = build(type, customers);
                extra.addAll(txns);
                cases.add(toCase(type, i, txns));
            }
        }
        return new Result(extra, cases);
    }

    // ---- scenario builders -------------------------------------------------------------------

    private List<PaymentTransaction> build(ScenarioType type, List<Customer> customers) {
        Customer payer = customers.get(random.nextInt(customers.size()));
        Customer payee = otherThan(payer, customers);
        Instant at = settings.startTime().plusSeconds((long) (random.nextDouble() * settings.spanHours() * 3600L));

        return switch (type) {
            case DEBIT_NOT_CREDITED_PENDING -> List.of(txn(Rail.UPI, money(200, 20_000), payer, payee,
                    TxnStatus.PENDING, FailureReason.NETWORK_TIMEOUT, at));
            case AUTO_REVERSAL_COMPLETED -> List.of(txn(Rail.UPI, money(200, 20_000), payer, payee,
                    TxnStatus.REVERSED, FailureReason.DEBIT_NOT_CREDITED, at));
            case DUPLICATE_DEBIT -> duplicateDebit(payer, payee, at);
            case DAILY_LIMIT_EXCEEDED -> List.of(txn(Rail.UPI, money(50_000, 100_000), payer, payee,
                    TxnStatus.FAILED, FailureReason.DAILY_LIMIT_EXCEEDED, at));
            case NEFT_CREDIT_DELAYED -> List.of(txn(Rail.NEFT, money(10_000, 500_000), payer, payee,
                    TxnStatus.PENDING, FailureReason.BENEFICIARY_BANK_DOWN, at));
            case MANDATE_DEBIT_FAILED -> List.of(txn(Rail.MANDATE, pickAmount(99, 199, 499, 999, 2500), payer, payee,
                    TxnStatus.FAILED, FailureReason.INSUFFICIENT_FUNDS, at));
            case CONFLICTING_EVIDENCE -> List.of(txn(Rail.UPI, money(500, 30_000), payer, payee,
                    TxnStatus.DEEMED_SUCCESS, FailureReason.NETWORK_TIMEOUT, at));
            case MULE_ACCOUNT_RING -> muleRing(customers, at);
            case BUSY_MERCHANT -> busyMerchant(customers, at);
            case SLOW_MULE -> slowMule(customers, at);
        };
    }

    /** Same payer, same payee, same amount, a few minutes apart: both succeed. */
    private List<PaymentTransaction> duplicateDebit(Customer payer, Customer payee, Instant at) {
        BigDecimal amount = money(300, 5_000);
        Instant second = at.plusSeconds(60 + random.nextInt(240));
        return List.of(
                txn(Rail.UPI, amount, payer, payee, TxnStatus.SUCCESS, null, at),
                txn(Rail.UPI, amount, payer, payee, TxnStatus.SUCCESS, null, second));
    }

    /**
     * 20-35 different senders pay small amounts (INR 300-900) to one payee inside two hours.
     * The payee forwards about 97% of each payment to one of two collector accounts within 1-5 minutes.
     */
    private List<PaymentTransaction> muleRing(List<Customer> customers, Instant windowStart) {
        List<Customer> pool = new ArrayList<>(customers);
        Collections.shuffle(pool, random);
        int senderCount = Math.min(20 + random.nextInt(16), pool.size() - 3);

        Customer mule = pool.get(0);
        List<Customer> collectors = pool.subList(1, 3);
        List<PaymentTransaction> txns = new ArrayList<>();

        for (Customer sender : pool.subList(3, 3 + senderCount)) {
            Instant inboundAt = windowStart.plusSeconds(random.nextInt(7_200));
            BigDecimal amount = money(300, 900);
            txns.add(txn(Rail.UPI, amount, sender, mule, TxnStatus.SUCCESS, null, inboundAt));

            BigDecimal forwarded = amount.multiply(new BigDecimal("0.97")).setScale(2, RoundingMode.HALF_UP);
            Instant outboundAt = inboundAt.plusSeconds(60 + random.nextInt(240));
            txns.add(txn(Rail.UPI, forwarded, mule, collectors.get(random.nextInt(2)),
                    TxnStatus.SUCCESS, null, outboundAt));
        }
        return txns;
    }

    private List<PaymentTransaction> busyMerchant(List<Customer> customers, Instant windowStart) {
        List<Customer> pool = new ArrayList<>(customers);
        Collections.shuffle(pool, random);
        int senderCount = Math.min(30 + random.nextInt(20), pool.size() - 1);

        Customer merchant = pool.get(0);
        List<PaymentTransaction> txns = new ArrayList<>();

        for (Customer sender : pool.subList(1, 1 + senderCount)) {
            Instant inboundAt = windowStart.plusSeconds(random.nextInt(7_200));
            BigDecimal amount = money(100, 2_000);

            // Note: NO outbound forwarding transaction is created here.
            txns.add(txn(Rail.UPI, amount, sender, merchant, TxnStatus.SUCCESS, null, inboundAt));
        }
        return txns;
    }

    private List<PaymentTransaction> slowMule(List<Customer> customers, Instant windowStart) {
        List<Customer> pool = new ArrayList<>(customers);
        Collections.shuffle(pool, random);
        int senderCount = Math.min(15 + random.nextInt(10), pool.size() - 3);

        Customer mule = pool.get(0);
        List<Customer> collectors = pool.subList(1, 3);
        List<PaymentTransaction> txns = new ArrayList<>();

        for (Customer sender : pool.subList(3, 3 + senderCount)) {
            Instant inboundAt = windowStart.plusSeconds(random.nextInt(7_200));
            BigDecimal amount = money(300, 900);
            txns.add(txn(Rail.UPI, amount, sender, mule, TxnStatus.SUCCESS, null, inboundAt));

            // Forwarded, but delayed by 3 to 12 hours
            BigDecimal forwarded = amount.multiply(new BigDecimal("0.97")).setScale(2, RoundingMode.HALF_UP);
            Instant outboundAt = inboundAt.plusSeconds(10_800 + random.nextInt(32_400));
            txns.add(txn(Rail.UPI, forwarded, mule, collectors.get(random.nextInt(2)),
                    TxnStatus.SUCCESS, null, outboundAt));
        }
        return txns;
    }

    // ---- case assembly -----------------------------------------------------------------------

    private ScenarioCase toCase(ScenarioType type, int index, List<PaymentTransaction> txns) {
        PaymentTransaction first = txns.get(0);
        String question = type.questionTemplate()
                .replace("{txnId}", first.txnId())
                .replace("{txnId2}", txns.size() > 1 ? txns.get(1).txnId() : first.txnId())
                .replace("{amount}", first.amountInr().toPlainString())
                .replace("{payee}", first.payeeId().toString());

        return new ScenarioCase(
                type.name() + "-" + String.format("%03d", index),
                type, type.title(),
                txns.stream().map(PaymentTransaction::txnId).toList(),
                question, type.expectedAction(), type.requiresApproval(), type.customerDebited(),
                type.expectedTimeline(), type.ruleTopic(), type.expectedFacts());
    }

    // ---- small helpers -----------------------------------------------------------------------

    private PaymentTransaction txn(Rail rail, BigDecimal amount, Customer payer, Customer payee,
                                   TxnStatus status, FailureReason reason, Instant at) {
        return new PaymentTransaction(uniqueId(rail), rail, amount, payer.customerId(), payee.customerId(),
                status, reason, at);
    }

    private String uniqueId(Rail rail) {
        String id;
        do {
            id = rail.idPrefix() + String.format("%012d", Math.floorMod(random.nextLong(), 1_000_000_000_000L));
        } while (!usedIds.add(id));
        return id;
    }

    private Customer otherThan(Customer other, List<Customer> customers) {
        Customer c;
        do {
            c = customers.get(random.nextInt(customers.size()));
        } while (c.customerId().equals(other.customerId()));
        return c;
    }

    private BigDecimal money(double min, double max) {
        return BigDecimal.valueOf(min + random.nextDouble() * (max - min)).setScale(2, RoundingMode.HALF_UP);
    }

    private BigDecimal pickAmount(int... options) {
        return BigDecimal.valueOf(options[random.nextInt(options.length)]).setScale(2, RoundingMode.HALF_UP);
    }
}
