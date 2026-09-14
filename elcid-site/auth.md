# auth.md for EL CID Country Club

## Agent registration
EL CID Country Club supports anonymous agent access for public, read-only hotel discovery. No account, OAuth token, API key, client secret or paid credential is required or issued for the public MCP and A2A endpoints.

```yaml
agent_auth:
  skill: public-read-only-hotel-discovery
  register_uri: https://www.elcidspain.com/auth.md#agent-registration
  methods:
    - type: anonymous
      credentials: none
      endpoints:
        - https://www.elcidspain.com/mcp
        - https://www.elcidspain.com/a2a
```

The `register_uri` documents the provisioning policy rather than creating an account: public agents are provisioned by anonymous access and use no credential. Protected or write-capable agent access is not offered.

## Reservations
The agent endpoints do not create, change or cancel reservations. Live dates, prices and conditions are confirmed through the public Booking.com or contact routes published by EL CID.

## Agent behaviour
Automated clients may read public hotel, restaurant, location and policy information subject to robots.txt, normal HTTP controls and rate limits. Do not infer an OAuth issuer, protected API, payment protocol or privileged credential flow that is not explicitly published.

Last updated: 2026-09-14
