package com.upisentinel.generator.domain;

/** What a correct agent should end up recommending for a scenario. Used later as the eval answer key. */
public enum ExpectedAction {
    WAIT_AND_MONITOR,          // money is in flight; wait for the rule's deadline, then escalate
    EXPLAIN_ONLY,              // nothing to fix; explain what happened
    RAISE_DUPLICATE_DISPUTE,   // write action: needs human approval
    ADVISE_RETRY,              // no money moved; customer can retry
    NOTIFY_AND_RETRY,          // recurring mandate failed; notify and follow retry rules
    ESCALATE_L2,               // evidence conflicts; the agent must not guess
    ESCALATE_FRAUD             // route to the fraud analyst, not a customer-refund flow
}
