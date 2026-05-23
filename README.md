<!-- mcp-name: io.github.SnipMCP/gadschain -->

# GadsChain

The AI layer between your Google Ads account and your marketing decisions.

**Battle-tested.** Six tools cover the daily-ops loop — campaign listing, search-term review, budget tuning, pause/enable, and negative-keyword grooming. All responses are strict Pydantic models. No raw protobuf reaches the agent.

![GadsChain Demo](demo/gadschain_demo.gif)

## ☁️ Moving to production?

The open-source server runs locally with your own API keys.
For hosted infrastructure with multi-account failover, SLA guarantees,
and webhook alerts — [join the managed cloud waitlist](https://snipmcp.com).

## The Problem

Raw Google Ads API returns thousands of rows. One bad campaign structure bleeds budget silently. GadsChain reads, sanitizes, and acts on your ad data before waste compounds.

## Installation

```bash
git clone https://github.com/SnipMCP/gadschain.git
cd gadschain
pip install -e ".[dev]"
cp .env.example .env
```

Or with Docker:

```bash
docker-compose up --build
```

## Configuration

```env
GOOGLE_ADS_DEVELOPER_TOKEN=your_developer_token_here
GOOGLE_ADS_CLIENT_ID=your_oauth_client_id_here
GOOGLE_ADS_CLIENT_SECRET=your_oauth_client_secret_here
GOOGLE_ADS_REFRESH_TOKEN=your_refresh_token_here
GOOGLE_ADS_LOGIN_CUSTOMER_ID=1234567890   # MCC (manager), digits only
GOOGLE_ADS_CUSTOMER_ID=1234567890         # default operating account
GOOGLE_ADS_API_VERSION=v24
LOG_LEVEL=INFO
```

## Usage

Three example prompts to send to Claude (or any MCP-compatible agent):

1. `Use get_campaigns to show me which campaigns are bleeding budget this month`
2. `Run get_search_terms for the last 30 days and tell me which queries are wasting spend`
3. `Add "free", "cheap", "jobs" as negative keywords to campaign 12345`

### Run it in two terminals

```bash
# Tab 1 — start the MCP server
python -m gadschain.server
```

```bash
# Tab 2 — call a tool from a Python shell or your MCP client
# Tool signatures:
#   get_campaigns(customer_id=None)
#   get_search_terms(customer_id=None, days=30, campaign_id=None)
#   update_budget(campaign_id, new_budget_dollars, customer_id=None)
#   pause_campaign(campaign_id, customer_id=None)
#   enable_campaign(campaign_id, customer_id=None)
#   add_negative_keywords(campaign_id, keywords, match_type="BROAD", customer_id=None)
```

## How it works

Three layers between raw Google Ads output and your model:

```
Google Ads API → [Fetch] → [Transform] → [Act] → MCP Tool → AI Agent
                  GAQL      micros→$       safe
                  queries   enum→str       mutations
                            CTR→%          shared-budget guard
```

- **Fetch**: Targeted GAQL queries — only the columns the daily-ops loop actually needs. No `SELECT *`, no protobuf pagination footguns.
- **Transform**: Currency micros divided to dollars, CTR scaled to percent, enums to human strings, every nested attribute lookup tolerates missing fields without crashing.
- **Act**: Mutations route through guard rails — `REMOVED` blocked on status changes, shared budgets refused (`shared_budget_refused`), match types validated before any mutate call. The agent never gets an exception; it gets a structured `{"error": ..., "message": ...}` it can reason about.

### Real numbers from a live Franka Pizzeria account (28-day window)

```
RAW GOOGLE ADS PAYLOAD          GADSCHAIN OUTPUT
─────────────────────────────────────────────────
Impressions:    3,389           Spend (28d):      $51.41
Clicks:         163             Conversions:      3 ($17.14 each)
CTR:            4.81%           Conv. rate:       1.84%
Cost/click:     $0.32 avg       Surface:          Display Network waste
                                                  identified on Fridays
                                                  ($0.11 CPC vs $0.44 avg)
```

In one read of a real account, GadsChain surfaced **$51.41 spent over 28 days for 3 conversions at $17.14 each** — a 1.84% conversion rate hidden inside a 4.81% CTR that looks healthy on paper. The Display Network was the silent culprit, with Friday clicks averaging **$0.11 CPC vs the $0.44 search-side average** — cheap junk traffic inflating CTR while contributing nothing to conversions. The agent saw it because the transformed payload made channel attribution legible instead of buried in protobuf.

## Roadmap

- Managed cloud tier (hosted, multi-tenant, webhook alerts)
- Phase 2: ChatGPT REST shim (FastAPI surface over the same six tools)
- Bid-strategy tuning tools (target CPA, target ROAS)
- Anomaly alerts on cost-per-conversion drift

## Contributing

PRs welcome. Run `pytest` before submitting.
