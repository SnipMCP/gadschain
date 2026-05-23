# GadsChain

Google Ads MCP server — clean, agent-friendly tools over the Google Ads API.

Six tools cover the daily-ops loop: campaign listing, search-term review, budget tuning, pause/enable, and negative-keyword grooming. All responses are strict Pydantic models — no raw protobuf leaks to the agent.

## Tools (Phase 1)

| Tool | Purpose |
|---|---|
| `get_campaigns(customer_id=None)` | List campaigns with status, daily budget, and core metrics |
| `get_search_terms(customer_id=None, days=30, campaign_id=None)` | Top 50 search terms by spend over the lookback window |
| `update_budget(campaign_id, new_budget_dollars, customer_id=None)` | Set daily budget (USD; converted to micros internally) |
| `pause_campaign(campaign_id, customer_id=None)` | Set status → `PAUSED` |
| `enable_campaign(campaign_id, customer_id=None)` | Set status → `ENABLED` |
| `add_negative_keywords(campaign_id, keywords, match_type="BROAD", customer_id=None)` | Batch-attach campaign-level negatives |

## Prerequisites

You need three things from Google before this can talk to the API:

1. **A Google Ads MCC (manager) account** — the "login" customer that has permission over the operating accounts.
2. **A developer token** — get one from your MCC at https://ads.google.com → Tools → API Center. New tokens start in test mode; request basic/standard access for production.
3. **OAuth2 credentials** — create an OAuth client (Web application or Desktop app) in Google Cloud Console, then complete the consent flow to obtain a `refresh_token`. Full walkthrough: https://developers.google.com/google-ads/api/docs/oauth/cloud-project

Shared budgets (`campaign_budget.explicitly_shared = true`) are refused by `update_budget` to avoid accidentally moving multiple campaigns at once.

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
GOOGLE_ADS_LOGIN_CUSTOMER_ID=1234567890     # MCC, digits only
GOOGLE_ADS_CUSTOMER_ID=1234567890           # default operating account (overridable per call)
GOOGLE_ADS_API_VERSION=v17                  # optional
LOG_LEVEL=INFO
```

Customer IDs can be passed dashed (`168-612-1194`) or undashed (`1686121194`) — the client strips dashes before sending.

## Run locally

```bash
# Tab 1 — start the MCP server
python -m gadschain.server
```

```bash
# Tab 2 — verify tests pass
pytest
```

## Connect to Claude

Add gadschain as an MCP server to Claude Desktop or Claude Code by editing `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or your Claude Code MCP settings:

```json
{
  "mcpServers": {
    "gadschain": {
      "command": "python",
      "args": ["-m", "gadschain.server"],
      "env": {
        "GOOGLE_ADS_DEVELOPER_TOKEN": "...",
        "GOOGLE_ADS_CLIENT_ID": "...",
        "GOOGLE_ADS_CLIENT_SECRET": "...",
        "GOOGLE_ADS_REFRESH_TOKEN": "...",
        "GOOGLE_ADS_LOGIN_CUSTOMER_ID": "1234567890",
        "GOOGLE_ADS_CUSTOMER_ID": "1234567890"
      }
    }
  }
}
```

Restart Claude. The six tools appear under `gadschain` and can be invoked directly: *"List my campaigns,"* *"Pause campaign 12345,"* *"Add 'free' as a negative keyword to all campaigns."*

## Connect to ChatGPT (Phase 2 — placeholder)

ChatGPT does not yet speak MCP natively. A REST shim is planned for Phase 2 — it will wrap the same six tools behind a small FastAPI surface so ChatGPT custom GPTs can call them via OpenAPI. Until then, point ChatGPT-based agents at the MCP server through an MCP-aware proxy (e.g., the Anthropic API with tool-use streaming, or a community bridge).

## Project layout

```
gadschain/
├── .env.example
├── Dockerfile / docker-compose.yml
├── pyproject.toml / LICENSE / README.md
├── src/gadschain/
│   ├── server.py              ← FastMCP entry + 6 tools
│   ├── clients/
│   │   ├── base.py            ← BaseAdsClient + AdsClientError
│   │   └── google_ads.py      ← GoogleAdsClient wrapper + GAQL + mutations
│   ├── core/
│   │   └── transformer.py     ← raw rows → Pydantic models
│   └── models/
│       └── campaign.py        ← Campaign, SearchTerm, *Result models
└── tests/
    ├── test_scaffold.py       ← MCP wiring smoke tests
    ├── test_implementation.py ← unit tests with google-ads mocked
    └── test_integration.py    ← live test (auto-skips without credentials)
```

## Testing

```bash
pytest                            # all unit + scaffold tests, integration auto-skipped
pytest tests/test_integration.py  # runs only if GOOGLE_ADS_DEVELOPER_TOKEN is set
```

The integration test targets the Franka Pizzeria account (`168-612-1194`) under the configured MCC; adjust if your account layout differs.

## License

MIT — see [LICENSE](LICENSE).
