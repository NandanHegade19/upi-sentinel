package com.upisentinel.generator.domain;

import java.util.List;

/**
 * The 8 scripted scenarios. Each one is a problem the agent must handle, plus the answer key.
 *
 * ruleTopic = what the retrieval step should find in the public documents (Week 2).
 * expectedFacts = statements a correct answer must contain (used by the LLM judge in Epic 7).
 * Real turnaround times and codes are deliberately NOT written here: they come from the
 * official documents, so the knowledge base stays the single source of truth.
 */
public enum ScenarioType {

    DEBIT_NOT_CREDITED_PENDING("Debited, not credited, still pending",
            ExpectedAction.WAIT_AND_MONITOR, true, false,
            List.of("INITIATED", "DEBITED", "PENDING"),
            "UPI failed or pending transaction: automatic reversal turnaround time",
            "Customer says INR {amount} was debited for transaction {txnId} but the merchant has not received it. What should we tell them?",
            List.of("Money was debited but the credit is not confirmed",
                    "The status is pending",
                    "Auto-reversal or credit is expected within the turnaround time in the rule",
                    "Do not refund manually before the deadline passes")),

    AUTO_REVERSAL_COMPLETED("Failed payment already reversed",
            ExpectedAction.EXPLAIN_ONLY, true, false,
            List.of("INITIATED", "DEBITED", "PENDING", "REVERSED"),
            "UPI failed transaction: automatic reversal to the customer's account",
            "Customer asks about transaction {txnId} of INR {amount}: the money left the account earlier. Is it lost?",
            List.of("The debit was reversed to the customer's account",
                    "No refund request or dispute is needed",
                    "Share the reversal confirmation with the customer")),

    DUPLICATE_DEBIT("Same payment charged twice",
            ExpectedAction.RAISE_DUPLICATE_DISPUTE, true, true,
            List.of("INITIATED", "DEBITED"),
            "Duplicate debit and how to raise a dispute for UPI payments",
            "Customer says INR {amount} was charged twice to the same merchant within minutes (transactions {txnId} and {txnId2}). Please help.",
            List.of("Two successful debits of the same amount to the same payee within minutes",
                    "The second payment looks like a duplicate",
                    "Raise a duplicate-payment dispute; this write action needs human approval")),

    DAILY_LIMIT_EXCEEDED("Failed because a limit was exceeded",
            ExpectedAction.ADVISE_RETRY, false, false,
            List.of("INITIATED", "FAILED"),
            "UPI transaction limits per day and per transaction",
            "Customer's payment {txnId} of INR {amount} failed. Was any money taken from the account?",
            List.of("The payment failed because a limit was exceeded",
                    "No money was debited",
                    "Advise retrying after the limit resets or using another account")),

    NEFT_CREDIT_DELAYED("NEFT sent, beneficiary has not received it",
            ExpectedAction.WAIT_AND_MONITOR, true, false,
            List.of("INITIATED", "DEBITED", "PENDING"),
            "NEFT settlement timing and credit to the beneficiary",
            "Customer sent INR {amount} by NEFT (transaction {txnId}) and the beneficiary says it has not arrived. What is the status?",
            List.of("NEFT settles in batches, so a short delay can be normal",
                    "Money was debited and the credit is pending",
                    "Check settlement timing and advise waiting unless the deadline has passed")),

    MANDATE_DEBIT_FAILED("Recurring mandate debit failed",
            ExpectedAction.NOTIFY_AND_RETRY, false, false,
            List.of("INITIATED", "FAILED"),
            "UPI AutoPay and e-mandate failed debit handling",
            "A recurring mandate debit of INR {amount} (transaction {txnId}) failed. What happened and what should we do?",
            List.of("The mandate debit failed because of insufficient funds",
                    "No money was debited",
                    "Notify the customer and follow the retry rules for mandates")),

    CONFLICTING_EVIDENCE("Status says success, merchant says nothing arrived",
            ExpectedAction.ESCALATE_L2, true, false,
            List.of("INITIATED", "DEBITED", "DEEMED_SUCCESS"),
            "Deemed success status and reconciliation with the beneficiary bank",
            "Transaction {txnId} (INR {amount}) shows deemed success but the merchant says nothing arrived. What is the truth?",
            List.of("The system status and the merchant's report disagree",
                    "The agent must not guess the outcome",
                    "Escalate to L2 with the evidence gathered")),

    MULE_ACCOUNT_RING("Many small payments into one payee, forwarded fast",
            ExpectedAction.ESCALATE_FRAUD, true, false,
            List.of("INITIATED", "DEBITED", "CREDITED"),
            "Mule account patterns and fraud monitoring guidance",
            "Payee {payee} received many small payments from different people within two hours and forwarded the money on quickly. Is this suspicious?",
            List.of("Many different senders paid the same payee in a short window",
                    "Payments were small and the payee forwarded the money quickly",
                    "Flag for fraud review; this is not a customer refund case")),

    BUSY_MERCHANT("High fan-in, no fan-out (Legitimate Merchant)",
                  ExpectedAction.EXPLAIN_ONLY, true, false,
                  List.of("INITIATED", "DEBITED", "CREDITED"),
            "Merchant payment velocity and legitimate business patterns",
                    "Payee {payee} received many payments within two hours but did not forward them. Is this a mule account?",
                    List.of("Many payments were received but the money was retained in the account",
                    "High fan-in without fast fan-out indicates a legitimate busy merchant",
                    "Do not flag as fraud")),

    SLOW_MULE("High fan-in, delayed fan-out (Evading Mule)",
              ExpectedAction.ESCALATE_FRAUD, true, false,
              List.of("INITIATED", "DEBITED", "CREDITED"),
            "Delayed mule account patterns and fraud monitoring",
                    "Payee {payee} received many payments and forwarded them after several hours. Should this be flagged?",
                    List.of("Payments were received and forwarded after a multi-hour delay",
                    "Delayed forwarding is a known tactic to evade fast-velocity rules",
                    "Flag for fraud review; this is not a customer refund case"));

    private final String title;
    private final ExpectedAction expectedAction;
    private final boolean customerDebited;
    private final boolean requiresApproval;
    private final List<String> expectedTimeline;
    private final String ruleTopic;
    private final String questionTemplate;
    private final List<String> expectedFacts;

    ScenarioType(String title, ExpectedAction expectedAction, boolean customerDebited, boolean requiresApproval,
                 List<String> expectedTimeline, String ruleTopic, String questionTemplate,
                 List<String> expectedFacts) {
        this.title = title;
        this.expectedAction = expectedAction;
        this.customerDebited = customerDebited;
        this.requiresApproval = requiresApproval;
        this.expectedTimeline = expectedTimeline;
        this.ruleTopic = ruleTopic;
        this.questionTemplate = questionTemplate;
        this.expectedFacts = expectedFacts;
    }

    public String title() { return title; }
    public ExpectedAction expectedAction() { return expectedAction; }
    public boolean customerDebited() { return customerDebited; }
    public boolean requiresApproval() { return requiresApproval; }
    public List<String> expectedTimeline() { return expectedTimeline; }
    public String ruleTopic() { return ruleTopic; }
    public String questionTemplate() { return questionTemplate; }
    public List<String> expectedFacts() { return expectedFacts; }
}
