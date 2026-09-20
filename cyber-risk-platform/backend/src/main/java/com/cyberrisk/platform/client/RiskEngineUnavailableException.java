package com.cyberrisk.platform.client;

/** Signals that the Python risk engine could not be reached or returned an error. */
public class RiskEngineUnavailableException extends RuntimeException {
    public RiskEngineUnavailableException(String message, Throwable cause) {
        super(message, cause);
    }
}
