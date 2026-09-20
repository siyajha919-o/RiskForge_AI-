package com.cyberrisk.platform.model;

/**
 * Application roles.
 * CISO added per the original requirements (business/executive persona)
 * — the previous implementation only had ADMIN, ANALYST, VIEWER.
 *
 * Ordering here is intentional: it's used as a coarse privilege rank
 * in a couple of helper checks below.
 */
public enum Role {
    VIEWER,   // read-only: dashboards, reports
    ANALYST,  // can create/update assets, vulnerabilities, controls
    CISO,     // analyst-level read/write + report generation + compliance views
    ADMIN;    // full access, including user/role management

    public boolean atLeast(Role other) {
        return this.ordinal() >= other.ordinal();
    }
}
