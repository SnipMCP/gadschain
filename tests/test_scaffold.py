"""Smoke tests confirming the scaffold wires up. No tool logic is exercised."""
import asyncio
import pytest

from gadschain.server import (
    mcp,
    get_campaigns,
    get_search_terms,
    update_budget,
    pause_campaign,
    enable_campaign,
    add_negative_keywords,
)


def test_mcp_server_instantiated():
    assert mcp.name == "gadschain"


@pytest.mark.asyncio
async def test_all_six_tools_registered():
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    assert names == {
        "get_campaigns",
        "get_search_terms",
        "update_budget",
        "pause_campaign",
        "enable_campaign",
        "add_negative_keywords",
    }


@pytest.mark.asyncio
async def test_missing_customer_id_returns_structured_error(monkeypatch):
    monkeypatch.delenv("GOOGLE_ADS_CUSTOMER_ID", raising=False)
    out = await get_campaigns()
    assert out["error"] == "missing_customer_id"


@pytest.mark.asyncio
async def test_invalid_match_type_rejected(monkeypatch):
    monkeypatch.setenv("GOOGLE_ADS_CUSTOMER_ID", "1234567890")
    out = await add_negative_keywords(campaign_id="c1", keywords=["a"], match_type="FUZZY")
    assert out["error"] == "invalid_match_type"
