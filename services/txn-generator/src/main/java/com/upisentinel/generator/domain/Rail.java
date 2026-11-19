package com.upisentinel.generator.domain;

/** Payment rails covered by the project. */
public enum Rail {
    UPI("UPI"), IMPS("IMP"), NEFT("NEF"), RTGS("RTG"), MANDATE("MND");

    private final String idPrefix;

    Rail(String idPrefix) {
        this.idPrefix = idPrefix;
    }

    public String idPrefix() {
        return idPrefix;
    }
}
