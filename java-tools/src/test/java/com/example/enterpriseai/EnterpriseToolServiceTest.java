package com.example.enterpriseai;

import static org.junit.jupiter.api.Assertions.*;
import org.junit.jupiter.api.Test;

class EnterpriseToolServiceTest {
    @Test
    void highValueActionRequiresApproval() {
        var service = new EnterpriseToolService();
        var risk = service.assessActionRisk("refund", 750);
        assertTrue(risk.approvalRequired());
        assertEquals("high", risk.riskLevel());
    }

    @Test
    void knownCustomerCanBeRead() {
        var service = new EnterpriseToolService();
        assertEquals("Contoso", service.getCustomer("CUST-1001").name());
    }
}
