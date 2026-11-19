package com.upisentinel.generator.domain;

import java.util.List;

/**
 * One golden-set item: a question, the transactions behind it, and the answer key.
 * expectedTimeline is consumed in US-1.3, when events are emitted.
 */
public record ScenarioCase(
        String caseId,
        ScenarioType scenario,
        String title,
        List<String> txnIds,
        String question,
        ExpectedAction expectedAction,
        boolean requiresApproval,
        boolean customerDebited,
        List<String> expectedTimeline,
        String ruleTopic,
        List<String> expectedFacts) {
}
