package com.upisentinel.generator;

import com.upisentinel.generator.domain.Customer;
import com.upisentinel.generator.domain.PaymentTransaction;
import com.upisentinel.generator.domain.ScenarioCase;
import com.upisentinel.generator.domain.ScenarioType;
import com.upisentinel.generator.domain.TxnStatus;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

import static org.assertj.core.api.Assertions.assertThat;

class ScenarioInjectorTest {

    private static GeneratorProperties settings(long seed, int perType) {
        return new GeneratorProperties(seed, 200, 2000, 0.08,
                Instant.parse("2026-01-01T00:00:00Z"), 24, perType, "output");
    }

    private record Run(List<Customer> customers, List<PaymentTransaction> base, ScenarioInjector.Result scenarios) {}

    private static Run run(GeneratorProperties s) {
        SyntheticDataGenerator g = new SyntheticDataGenerator(s);
        List<Customer> customers = g.generateCustomers();
        List<PaymentTransaction> base = g.generateTransactions(customers);
        return new Run(customers, base, new ScenarioInjector(s).inject(customers, base));
    }

    @Test
    void hasAtLeastEightScenarioTypes() {
        assertThat(ScenarioType.values().length).isGreaterThanOrEqualTo(8);
    }

    @Test
    void createsTheRequestedNumberOfCasesPerType() {
        List<ScenarioCase> cases = run(settings(1, 5)).scenarios().cases();
        Map<ScenarioType, Long> perType = cases.stream()
                .collect(Collectors.groupingBy(ScenarioCase::scenario, Collectors.counting()));
        assertThat(perType).hasSize(ScenarioType.values().length);
        assertThat(perType.values()).allMatch(n -> n == 5);
    }

    @Test
    void everyCaseCarriesItsAnswerKey() {
        for (ScenarioCase c : run(settings(2, 3)).scenarios().cases()) {
            assertThat(c.expectedAction()).isNotNull();
            assertThat(c.expectedFacts()).isNotEmpty();
            assertThat(c.ruleTopic()).isNotBlank();
            assertThat(c.question()).doesNotContain("{");   // every placeholder was filled
            assertThat(c.txnIds()).isNotEmpty();
        }
    }

    @Test
    void caseTransactionsExistAndAllIdsAreUnique() {
        Run r = run(settings(3, 5));
        Set<String> extraIds = r.scenarios().transactions().stream()
                .map(PaymentTransaction::txnId).collect(Collectors.toSet());
        assertThat(extraIds).hasSize(r.scenarios().transactions().size());
        Set<String> all = new HashSet<>(extraIds);
        r.base().forEach(t -> assertThat(all.add(t.txnId())).as("id clash with base data").isTrue());
        r.scenarios().cases().forEach(c -> assertThat(extraIds).containsAll(c.txnIds()));
    }

    @Test
    void baseDataIsUnchangedByScenarios() {
        assertThat(run(settings(4, 0)).base()).isEqualTo(run(settings(4, 5)).base());
    }

    @Test
    void sameSeedGivesIdenticalScenarios() {
        Run a = run(settings(5, 5)), b = run(settings(5, 5));
        assertThat(a.scenarios().cases()).isEqualTo(b.scenarios().cases());
        assertThat(a.scenarios().transactions()).isEqualTo(b.scenarios().transactions());
    }

    @Test
    void zeroScenariosMeansNothingIsAdded() {
        Run r = run(settings(6, 0));
        assertThat(r.scenarios().cases()).isEmpty();
        assertThat(r.scenarios().transactions()).isEmpty();
    }

    @Test
    void duplicateDebitIsTwoIdenticalSuccessfulPayments() {
        Run r = run(settings(7, 5));
        Map<String, PaymentTransaction> byId = r.scenarios().transactions().stream()
                .collect(Collectors.toMap(PaymentTransaction::txnId, t -> t));
        for (ScenarioCase c : cases(r, ScenarioType.DUPLICATE_DEBIT)) {
            assertThat(c.txnIds()).hasSize(2);
            PaymentTransaction a = byId.get(c.txnIds().get(0)), b = byId.get(c.txnIds().get(1));
            assertThat(a.payerId()).isEqualTo(b.payerId());
            assertThat(a.payeeId()).isEqualTo(b.payeeId());
            assertThat(a.amountInr()).isEqualTo(b.amountInr());
            assertThat(a.currentStatus()).isEqualTo(TxnStatus.SUCCESS);
            assertThat(b.currentStatus()).isEqualTo(TxnStatus.SUCCESS);
            assertThat(c.requiresApproval()).isTrue();
        }
    }

    @Test
    void muleRingHasManySendersOneReceiverAndFastForwarding() {
        Run r = run(settings(8, 5));
        Map<String, PaymentTransaction> byId = r.scenarios().transactions().stream()
                .collect(Collectors.toMap(PaymentTransaction::txnId, t -> t));
        for (ScenarioCase c : cases(r, ScenarioType.MULE_ACCOUNT_RING)) {
            List<PaymentTransaction> txns = c.txnIds().stream().map(byId::get).toList();
            Map<Object, Long> receivedBy = txns.stream()
                    .collect(Collectors.groupingBy(PaymentTransaction::payeeId, Collectors.counting()));
            Object mule = receivedBy.entrySet().stream().max(Map.Entry.comparingByValue()).get().getKey();
            List<PaymentTransaction> inbound = txns.stream().filter(t -> t.payeeId().equals(mule)).toList();
            assertThat(inbound.stream().map(PaymentTransaction::payerId).distinct().count()).isGreaterThanOrEqualTo(20);
            assertThat(inbound).allMatch(t -> t.amountInr().compareTo(new BigDecimal("300")) >= 0
                    && t.amountInr().compareTo(new BigDecimal("900")) <= 0);
            assertThat(txns.stream().filter(t -> t.payerId().equals(mule)).count()).isEqualTo(inbound.size());
        }
    }

    @Test
    void casesWhereNoMoneyMovedHaveNoDebitInTheirTimeline() {
        for (ScenarioCase c : run(settings(9, 2)).scenarios().cases()) {
            if (!c.customerDebited()) assertThat(c.expectedTimeline()).doesNotContain("DEBITED");
            else assertThat(c.expectedTimeline()).contains("DEBITED");
        }
    }

    private static List<ScenarioCase> cases(Run r, ScenarioType type) {
        return r.scenarios().cases().stream().filter(c -> c.scenario() == type).toList();
    }
}
