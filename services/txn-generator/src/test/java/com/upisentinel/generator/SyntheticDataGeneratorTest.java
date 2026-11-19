package com.upisentinel.generator;

import com.upisentinel.generator.domain.Customer;
import com.upisentinel.generator.domain.PaymentTransaction;
import com.upisentinel.generator.domain.Rail;
import com.upisentinel.generator.domain.TxnStatus;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class SyntheticDataGeneratorTest {

    private static GeneratorProperties settings(long seed, int txns, double failureRate) {
        return new GeneratorProperties(seed, 100, txns, failureRate,
                Instant.parse("2026-01-01T00:00:00Z"), 24, 0, "output");
    }

    private record Data(List<Customer> customers, List<PaymentTransaction> txns) {}

    private static Data generate(GeneratorProperties s) {
        SyntheticDataGenerator g = new SyntheticDataGenerator(s);
        List<Customer> customers = g.generateCustomers();
        return new Data(customers, g.generateTransactions(customers));
    }

    @Test
    void sameSeedGivesIdenticalData() {
        Data a = generate(settings(7, 2000, 0.1));
        Data b = generate(settings(7, 2000, 0.1));
        assertThat(a.customers()).isEqualTo(b.customers());
        assertThat(a.txns()).isEqualTo(b.txns());
    }

    @Test
    void differentSeedGivesDifferentData() {
        assertThat(generate(settings(1, 500, 0.1)).txns())
                .isNotEqualTo(generate(settings(2, 500, 0.1)).txns());
    }

    @Test
    void producesRequestedVolume() {
        Data d = generate(settings(3, 1234, 0.1));
        assertThat(d.customers()).hasSize(100);
        assertThat(d.txns()).hasSize(1234);
    }

    @Test
    void failureRateIsRoughlyRespected() {
        List<PaymentTransaction> txns = generate(settings(4, 20_000, 0.10)).txns();
        long nonSuccess = txns.stream().filter(t -> t.currentStatus() != TxnStatus.SUCCESS).count();
        assertThat(nonSuccess / 20_000.0).isBetween(0.08, 0.12);
    }

    @Test
    void zeroFailureRateMeansAllSuccessWithNoReason() {
        List<PaymentTransaction> txns = generate(settings(5, 1000, 0.0)).txns();
        assertThat(txns).allMatch(t -> t.currentStatus() == TxnStatus.SUCCESS && t.failureReason() == null);
    }

    @Test
    void everyRailAppearsAndEveryNonSuccessHasAReason() {
        List<PaymentTransaction> txns = generate(settings(6, 20_000, 0.2)).txns();
        Set<Rail> rails = new HashSet<>();
        txns.forEach(t -> rails.add(t.rail()));
        assertThat(rails).containsExactlyInAnyOrder(Rail.values());
        assertThat(txns).filteredOn(t -> t.currentStatus() != TxnStatus.SUCCESS)
                .allMatch(t -> t.failureReason() != null);
    }

    @Test
    void rtgsAmountsRespectHighMinimumAndAllAmountsArePositive() {
        List<PaymentTransaction> txns = generate(settings(8, 20_000, 0.1)).txns();
        assertThat(txns).allMatch(t -> t.amountInr().signum() > 0);
        assertThat(txns).filteredOn(t -> t.rail() == Rail.RTGS)
                .allMatch(t -> t.amountInr().compareTo(new BigDecimal("200000")) >= 0);
    }

    @Test
    void payerAndPayeeDifferAndTxnIdsAreUniqueAndTimeOrdered() {
        List<PaymentTransaction> txns = generate(settings(9, 5000, 0.1)).txns();
        assertThat(txns).allMatch(t -> !t.payerId().equals(t.payeeId()));
        assertThat(txns.stream().map(PaymentTransaction::txnId).distinct().count()).isEqualTo(5000);
        for (int i = 1; i < txns.size(); i++) {
            assertThat(txns.get(i).createdAt()).isAfterOrEqualTo(txns.get(i - 1).createdAt());
        }
    }

    @Test
    void invalidSettingsAreRejected() {
        assertThatThrownBy(() -> settings(1, 10, 1.5)).isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> settings(1, 0, 0.1)).isInstanceOf(IllegalArgumentException.class);
    }
}
