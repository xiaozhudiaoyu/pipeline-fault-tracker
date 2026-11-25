package com.example.fault;

import com.fasterxml.jackson.annotation.JsonValue;

public enum FaultRole {

    USER("user"),
    HANDLER("handler"),
    ADMIN("admin");

    private final String value;

    FaultRole(String value) {
        this.value = value;
    }

    @JsonValue
    public String getValue() {
        return value;
    }

    public static FaultRole fromValue(String value) {
        for (FaultRole role : FaultRole.values()) {
            if (role.value.equalsIgnoreCase(value)) {
                return role;
            }
        }
        throw new IllegalArgumentException("Unknown FaultRole value: " + value);
    }
}