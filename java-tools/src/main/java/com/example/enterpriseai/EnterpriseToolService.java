package com.example.enterpriseai;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

import org.springframework.ai.tool.annotation.Tool;
import org.springframework.ai.tool.annotation.ToolParam;
import org.springframework.stereotype.Service;

@Service
public class EnterpriseToolService {
    private final Map<String, Ticket> tickets = new ConcurrentHashMap<>();
    private final Map<String, Customer> customers = new ConcurrentHashMap<>();

    public EnterpriseToolService() {
        customers.put("CUST-1001",
                new Customer("CUST-1001", "Contoso", "enterprise", "active"));
    }

    @Tool(description = "Look up a customer by customer id. Read-only.")
    public Customer getCustomer(
            @ToolParam(description = "Customer id, for example CUST-1001") String customerId) {
        return customers.getOrDefault(customerId,
                new Customer(customerId, "unknown", "unknown", "not_found"));
    }

    @Tool(description = "Create a support ticket. This changes enterprise state.")
    public Ticket createSupportTicket(
            @ToolParam(description = "Customer id") String customerId,
            @ToolParam(description = "Short issue title") String title,
            @ToolParam(description = "Detailed issue description") String description,
            @ToolParam(description = "Priority: low, medium, high, critical") String priority) {
        String id = "T-" + UUID.randomUUID().toString().substring(0, 8);
        Ticket ticket = new Ticket(id, customerId, title, description, priority,
                "open", Instant.now().toString());
        tickets.put(id, ticket);
        return ticket;
    }

    @Tool(description = "Get a support ticket by id. Read-only.")
    public Ticket getTicket(@ToolParam(description = "Ticket id") String ticketId) {
        return tickets.getOrDefault(ticketId,
                new Ticket(ticketId, "", "", "", "", "not_found", ""));
    }

    @Tool(description = "Calculate risk for a requested action. Read-only; use before sensitive actions.")
    public RiskAssessment assessActionRisk(
            @ToolParam(description = "Action type") String action,
            @ToolParam(description = "Monetary amount if applicable") double amount) {
        boolean approval = amount >= 500 || action.toLowerCase().contains("delete")
                || action.toLowerCase().contains("refund");
        String level = approval ? "high" : amount >= 100 ? "medium" : "low";
        return new RiskAssessment(level, approval,
                approval ? "Human approval required before execution." : "May proceed under policy.");
    }

    public record Customer(String id, String name, String tier, String status) {}
    public record Ticket(String id, String customerId, String title, String description,
                         String priority, String status, String createdAt) {}
    public record RiskAssessment(String riskLevel, boolean approvalRequired, String reason) {}
}
