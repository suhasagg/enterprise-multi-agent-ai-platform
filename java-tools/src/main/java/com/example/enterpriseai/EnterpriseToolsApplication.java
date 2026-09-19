package com.example.enterpriseai;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;
import org.springframework.ai.tool.ToolCallbackProvider;
import org.springframework.ai.tool.method.MethodToolCallbackProvider;

@SpringBootApplication
public class EnterpriseToolsApplication {
    public static void main(String[] args) {
        SpringApplication.run(EnterpriseToolsApplication.class, args);
    }

    @Bean
    ToolCallbackProvider enterpriseTools(EnterpriseToolService service) {
        return MethodToolCallbackProvider.builder()
                .toolObjects(service)
                .build();
    }
}
