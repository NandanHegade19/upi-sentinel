package com.upisentinel.generator.domain;

/** Final state of a synthetic transaction. Timelines of intermediate states arrive in US-1.3. */
public enum TxnStatus {
    SUCCESS, FAILED, PENDING, REVERSED, DEEMED_SUCCESS
}
