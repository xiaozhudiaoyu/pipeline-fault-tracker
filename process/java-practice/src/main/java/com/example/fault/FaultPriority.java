package com.example.fault;

import com.fasterxml.jackson.annotation.JsonValue;

public enum FaultPriority {

    NORMAL("normal"),
    URGENT("urgent");

    private final String value;

    FaultPriority(String value) {
        this.value = value;
    }

    @JsonValue
    public String getValue() {
        return value;
    }
}