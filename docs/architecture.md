# AlphaFund AI — Hosting and execution architecture

## Chosen deployment

- **Dashboard:** Streamlit Community Cloud.
- **Initial Groww scope:** read-only holdings and CASH positions.
- **Trading:** paper mode only; live order placement remains disabled.
- **Credentials:** Streamlit server-side Secrets; never in GitHub, browser inputs, source code, or chat.

## Why Streamlit Community Cloud is not the future order host

Streamlit Community Cloud documents a set of outbound IP addresses but explicitly warns that these addresses may change without notice. Therefore, do not register a Community Cloud address as Groww's static IP for order placement. The current deployment is suitable for the dashboard and read-only portfolio access, not a dependable static-IP execution origin.

## Future design when live trading is separately approved

```text
Android browser
    | HTTPS
    v
Streamlit Community Cloud (dashboard / analytics / read-only view)
    | authenticated HTTPS API
    v
Private execution backend on VPS / cloud VM
    | fixed reserved public IPv4 (outbound)
    v
Groww API (IP whitelist)
```

### Backend requirements before any live orders

1. Provision a VPS or cloud VM with a reserved static public IPv4 address.
2. Confirm outbound requests originate from that exact address and register it in Groww's API key settings.
3. Store Groww credentials only in the execution backend's secret manager/environment, never in Streamlit client state.
4. Authenticate and authorize every dashboard-to-backend request; use HTTPS, request signing or short-lived service tokens, rate limits, audit logs, and secret redaction.
5. Add explicit risk controls: max order value, max daily loss, symbol allowlist, quantity limits, duplicate-order protection, market-hours checks, kill switch, and human confirmation.
6. Implement broker order status reconciliation and daily session/token lifecycle handling.
7. Run paper/sandbox tests and operational checks before requesting explicit approval to enable live order placement.

## Static IP note

Groww's static-IP requirement applies to API order placement. Streamlit Community Cloud publishes egress IPs but warns they can change without notice. The future execution backend therefore needs its own static IP. A secondary static IP can be considered for failover only if Groww supports registering it for the account/API key.

## Current boundary

The current `alphafund/groww_client.py` is read-only and implements only GET requests for holdings and CASH positions. It has no order methods. Do not add order placement to the Streamlit app. Build it as a separate backend service only after the user explicitly approves the live-trading phase.

## References

- Groww static IP setup: https://groww.in/blog/static-ip-api-trading-setup
- Streamlit Community Cloud IP limitations: https://docs.streamlit.io/deploy/streamlit-community-cloud/status
- Streamlit deployment and secrets: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
