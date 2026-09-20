package com.cyberrisk.platform.config;

import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.ClientHttpResponse;
import org.springframework.web.client.ResponseErrorHandler;
import org.springframework.web.client.RestTemplate;

import java.time.Duration;

@Configuration
public class RestClientConfig {

    /**
     * Timeouts are mandatory here: POST /api/v1/recompute can run for minutes
     * while TensorFlow trains, and an untimed client would hold a request
     * thread indefinitely if the engine hangs.
     */
    @Bean
    public RestTemplate riskEngineRestTemplate(RestTemplateBuilder builder) {
        return builder
                .setConnectTimeout(Duration.ofSeconds(5))
                .setReadTimeout(Duration.ofMinutes(5))
                .build();
    }

    /**
     * Client for the transparent gateway passthrough. Unlike the one above it
     * never throws on a non-2xx: a proxy has to relay the engine's own status
     * and body to the caller, and the default error handler would turn a 404 or
     * a 422 from the engine into a 500 from the gateway.
     */
    @Bean
    public RestTemplate gatewayProxyRestTemplate(RestTemplateBuilder builder) {
        RestTemplate template = builder
                .setConnectTimeout(Duration.ofSeconds(5))
                .setReadTimeout(Duration.ofMinutes(5))
                .build();
        template.setErrorHandler(new ResponseErrorHandler() {
            @Override
            public boolean hasError(ClientHttpResponse response) {
                return false;
            }

            @Override
            public void handleError(ClientHttpResponse response) {
                // Never called: hasError always reports false so the response
                // is relayed verbatim.
            }
        });
        return template;
    }
}
