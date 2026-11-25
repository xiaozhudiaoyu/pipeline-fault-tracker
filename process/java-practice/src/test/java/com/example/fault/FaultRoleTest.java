package com.example.fault;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

class FaultRoleTest {

    private final ObjectMapper mapper = new ObjectMapper();

    @Test
    @DisplayName("ADMIN 序列化成小写串 \"admin\"（对齐 Python 继承 str 的行为）")
    void serializesToLowerCase() throws Exception {
        assertEquals("\"admin\"", mapper.writeValueAsString(FaultRole.ADMIN));
        assertEquals(FaultRole.ADMIN, FaultRole.fromValue("admin"));
    }
}