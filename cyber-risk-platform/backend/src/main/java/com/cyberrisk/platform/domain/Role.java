package com.cyberrisk.platform.domain;

/**
 * Application roles, ordered least- to most-privileged.
 *
 * CISO is present because the problem statement names it as a distinct
 * persona: analyst-level read/write plus compliance and reporting views.
 */
public enum Role {
    VIEWER,
    ANALYST,
    CISO,
    ADMIN
}
