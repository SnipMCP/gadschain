from fastmcp import FastMCP
from dotenv import load_dotenv
import os
import logging
from typing import Optional

from .clients.base import AdsClientError
from .clients.google_ads import GoogleAdsClientWrapper, VALID_MATCH_TYPES
from .core.transformer import Transformer
from .models.campaign import CampaignList, SearchTermList

mcp = FastMCP("gadschain")

_client = GoogleAdsClientWrapper()
_transformer = Transformer()


def _resolve_customer_id(customer_id: Optional[str]) -> str:
    return customer_id or os.getenv("GOOGLE_ADS_CUSTOMER_ID", "")


def _handle_ads_exception(exc: Exception) -> dict:
    """Convert any ads-related exception to a structured dict."""
    if isinstance(exc, AdsClientError):
        return {"error": exc.code or "ads_client_error", "message": str(exc)}
    # GoogleAdsException is from the live library; import lazily so it's optional.
    try:
        from google.ads.googleads.errors import GoogleAdsException
    except ImportError:
        GoogleAdsException = None  # type: ignore
    if GoogleAdsException is not None and isinstance(exc, GoogleAdsException):
        return {
            "error": "google_ads_api_error",
            "message": str(exc),
            "request_id": getattr(exc, "request_id", None),
        }
    return {"error": "unexpected_error", "message": f"{type(exc).__name__}: {exc}"}


# ── Read tools ───────────────────────────────────────────────────────────────


@mcp.tool()
async def get_campaigns(customer_id: Optional[str] = None) -> dict:
    """List campaigns for a Google Ads customer with status, budget, and core metrics."""
    cid = _resolve_customer_id(customer_id)
    if not cid:
        return {"error": "missing_customer_id", "message": "Provide customer_id or set GOOGLE_ADS_CUSTOMER_ID."}
    try:
        rows = _client.list_campaigns(cid)
        campaigns = [_transformer.campaign_from_row(r) for r in rows]
        result = CampaignList(
            customer_id=str(cid),
            campaigns=campaigns,
            total_count=len(campaigns),
        )
        return result.model_dump()
    except Exception as e:
        return _handle_ads_exception(e)


@mcp.tool()
async def get_search_terms(
    customer_id: Optional[str] = None,
    days: int = 30,
    campaign_id: Optional[str] = None,
) -> dict:
    """Return search-term performance for the given lookback window (default 30 days)."""
    cid = _resolve_customer_id(customer_id)
    if not cid:
        return {"error": "missing_customer_id", "message": "Provide customer_id or set GOOGLE_ADS_CUSTOMER_ID."}
    try:
        rows = _client.list_search_terms(cid, days=days, campaign_id=campaign_id)
        terms = [_transformer.search_term_from_row(r) for r in rows]
        result = SearchTermList(
            customer_id=str(cid),
            terms=terms,
            total_count=len(terms),
            date_range=f"last_{days}_days",
        )
        return result.model_dump()
    except Exception as e:
        return _handle_ads_exception(e)


# ── Mutate tools ─────────────────────────────────────────────────────────────


@mcp.tool()
async def update_budget(
    campaign_id: str,
    new_budget_dollars: float,
    customer_id: Optional[str] = None,
) -> dict:
    """Set a campaign's daily budget. Amount is in dollars; converted to micros internally."""
    cid = _resolve_customer_id(customer_id)
    if not cid:
        return {"error": "missing_customer_id", "message": "Provide customer_id or set GOOGLE_ADS_CUSTOMER_ID."}
    try:
        raw = _client.update_campaign_budget(cid, campaign_id, float(new_budget_dollars))
        result = _transformer.budget_result(
            customer_id=cid,
            campaign_id=campaign_id,
            previous_micros=raw.get("previous_micros"),
            new_micros=raw.get("new_micros", int(round(new_budget_dollars * 1_000_000))),
            success=True,
            message=raw.get("resource_name"),
        )
        return result.model_dump()
    except Exception as e:
        return _handle_ads_exception(e)


@mcp.tool()
async def pause_campaign(
    campaign_id: str,
    customer_id: Optional[str] = None,
) -> dict:
    """Pause a campaign (sets status=PAUSED)."""
    cid = _resolve_customer_id(customer_id)
    if not cid:
        return {"error": "missing_customer_id", "message": "Provide customer_id or set GOOGLE_ADS_CUSTOMER_ID."}
    try:
        raw = _client.set_campaign_status(cid, campaign_id, "PAUSED")
        result = _transformer.status_result(
            customer_id=cid,
            campaign_id=campaign_id,
            new_status="PAUSED",
            success=True,
            message=raw.get("resource_name"),
        )
        return result.model_dump()
    except Exception as e:
        return _handle_ads_exception(e)


@mcp.tool()
async def enable_campaign(
    campaign_id: str,
    customer_id: Optional[str] = None,
) -> dict:
    """Enable a paused campaign (sets status=ENABLED)."""
    cid = _resolve_customer_id(customer_id)
    if not cid:
        return {"error": "missing_customer_id", "message": "Provide customer_id or set GOOGLE_ADS_CUSTOMER_ID."}
    try:
        raw = _client.set_campaign_status(cid, campaign_id, "ENABLED")
        result = _transformer.status_result(
            customer_id=cid,
            campaign_id=campaign_id,
            new_status="ENABLED",
            success=True,
            message=raw.get("resource_name"),
        )
        return result.model_dump()
    except Exception as e:
        return _handle_ads_exception(e)


@mcp.tool()
async def add_negative_keywords(
    campaign_id: str,
    keywords: list[str],
    match_type: str = "BROAD",
    customer_id: Optional[str] = None,
) -> dict:
    """Attach campaign-level negative keywords. match_type: EXACT | PHRASE | BROAD."""
    cid = _resolve_customer_id(customer_id)
    if not cid:
        return {"error": "missing_customer_id", "message": "Provide customer_id or set GOOGLE_ADS_CUSTOMER_ID."}
    mt = (match_type or "BROAD").upper()
    if mt not in VALID_MATCH_TYPES:
        return {
            "error": "invalid_match_type",
            "message": f"match_type must be one of {sorted(VALID_MATCH_TYPES)}. Got '{match_type}'.",
        }
    try:
        raw = _client.add_negative_keywords(cid, campaign_id, keywords, match_type=mt)
        result = _transformer.negative_keyword_result(
            customer_id=cid,
            campaign_id=campaign_id,
            keywords=raw.get("keywords_added", keywords),
            match_type=mt,
            count=raw.get("count", 0),
            success=True,
            message=", ".join(raw.get("resource_names", [])) or None,
        )
        return result.model_dump()
    except Exception as e:
        return _handle_ads_exception(e)


def main():
    load_dotenv()
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

    required = [
        "GOOGLE_ADS_DEVELOPER_TOKEN",
        "GOOGLE_ADS_CLIENT_ID",
        "GOOGLE_ADS_CLIENT_SECRET",
        "GOOGLE_ADS_REFRESH_TOKEN",
    ]
    for var in required:
        if not os.getenv(var):
            logging.warning("%s not set — gadschain tools will fail at runtime", var)

    mcp.run()


if __name__ == "__main__":
    main()
