"""Unit tests with the google-ads client mocked at the service level."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import pytest

from gadschain.clients.google_ads import GoogleAdsClientWrapper
from gadschain.clients.base import AdsClientError
from gadschain.core.transformer import Transformer
from gadschain.models.campaign import (
    CampaignList,
    SearchTermList,
    CampaignStatus,
)
from gadschain import server


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _make_campaign_row(
    id_=1,
    name="Test",
    status="ENABLED",
    budget_micros=50_000_000,
    impressions=1000,
    clicks=23,
    ctr=0.023,
    cost_micros=12_345_678,
    avg_cpc=536_899,
    conversions=2.0,
    cost_per_conv=6.17,
    channel="SEARCH",
    bidding="MAXIMIZE_CONVERSIONS",
):
    """Build a SimpleNamespace mimicking a google-ads GAQL row."""
    return SimpleNamespace(
        campaign=SimpleNamespace(
            id=id_,
            name=name,
            status=SimpleNamespace(name=status),
            advertising_channel_type=SimpleNamespace(name=channel),
            bidding_strategy_type=SimpleNamespace(name=bidding),
            start_date="2026-01-01",
            end_date=None,
        ),
        campaign_budget=SimpleNamespace(amount_micros=budget_micros),
        metrics=SimpleNamespace(
            impressions=impressions,
            clicks=clicks,
            ctr=ctr,
            average_cpc=avg_cpc,
            cost_micros=cost_micros,
            conversions=conversions,
            cost_per_conversion=cost_per_conv,
        ),
    )


def _make_search_term_row(term="pizza near me", cost_micros=1_000_000, campaign_id=42, ad_group_id=7):
    return SimpleNamespace(
        search_term_view=SimpleNamespace(search_term=term),
        metrics=SimpleNamespace(
            clicks=10,
            impressions=200,
            ctr=0.05,
            average_cpc=100_000,
            cost_micros=cost_micros,
            conversions=1.0,
        ),
        campaign=SimpleNamespace(id=campaign_id, name="Pizza Sales"),
        ad_group=SimpleNamespace(id=ad_group_id),
    )


@pytest.fixture
def mock_client():
    """Patch _ensure_client so no real auth is attempted."""
    with patch.object(GoogleAdsClientWrapper, "_ensure_client") as m:
        google_ads = MagicMock()
        m.return_value = google_ads
        yield google_ads


@pytest.fixture(autouse=True)
def reset_server_singletons(monkeypatch):
    """Each test gets a fresh wrapper so mocks don't leak."""
    monkeypatch.setattr(server, "_client", GoogleAdsClientWrapper())


# ── Field mapping & micros conversion ────────────────────────────────────────


def test_list_campaigns_returns_campaignlist_with_field_mapping(mock_client):
    ga_service = MagicMock()
    ga_service.search.return_value = iter([
        _make_campaign_row(id_=1, name="A", cost_micros=10_000_000, budget_micros=50_000_000),
        _make_campaign_row(id_=2, name="B", cost_micros=5_000_000, budget_micros=25_000_000),
    ])
    mock_client.get_service.return_value = ga_service

    rows = server._client.list_campaigns("123-456-7890")
    t = Transformer()
    campaigns = [t.campaign_from_row(r) for r in rows]
    cl = CampaignList(customer_id="1234567890", campaigns=campaigns, total_count=len(campaigns))

    assert cl.total_count == 2
    assert cl.campaigns[0].id == "1"
    assert cl.campaigns[0].cost_micros == 10_000_000
    assert cl.campaigns[0].cost_dollars == 10.00
    assert cl.campaigns[0].daily_budget_dollars == 50.00
    assert cl.campaigns[0].ctr_percent == 2.3  # 0.023 → 2.3%
    assert cl.campaigns[0].status == CampaignStatus.ENABLED


def test_list_search_terms_filters_by_campaign_id(mock_client):
    ga_service = MagicMock()
    ga_service.search.return_value = iter([_make_search_term_row(campaign_id=99)])
    mock_client.get_service.return_value = ga_service

    server._client.list_search_terms("1234567890", days=14, campaign_id="99")

    # Verify the GAQL sent contained the campaign filter and date range
    sent_query = ga_service.search.call_args.kwargs["query"]
    assert "campaign.id = 99" in sent_query
    assert "search_term_view" in sent_query
    assert "BETWEEN" in sent_query


def test_search_term_transformer_mapping():
    t = Transformer()
    row = _make_search_term_row(term="pizza", cost_micros=2_500_000)
    out = t.search_term_from_row(row)
    assert out.search_term == "pizza"
    assert out.cost_micros == 2_500_000
    assert out.cost_dollars == 2.50
    assert out.ctr_percent == 5.0


# ── Budget mutation: USD → micros ────────────────────────────────────────────


def test_update_campaign_budget_converts_usd_to_micros(mock_client):
    # First call: get_campaign_budget. Second call: mutate.
    budget_row = SimpleNamespace(
        campaign_budget=SimpleNamespace(
            id=999, amount_micros=100_000_000, explicitly_shared=False
        )
    )
    ga_service = MagicMock()
    ga_service.search.return_value = iter([budget_row])

    budget_service = MagicMock()
    budget_service.campaign_budget_path.return_value = "customers/1/campaignBudgets/999"
    mutate_response = MagicMock()
    mutate_response.results = [MagicMock(resource_name="customers/1/campaignBudgets/999")]
    budget_service.mutate_campaign_budgets.return_value = mutate_response

    def service_router(name):
        return ga_service if name == "GoogleAdsService" else budget_service

    mock_client.get_service.side_effect = service_router
    mock_client.get_type.return_value = MagicMock()
    mock_client.enums = MagicMock()

    with patch("google.api_core.protobuf_helpers.field_mask", return_value=MagicMock()):
        result = server._client.update_campaign_budget("1234567890", "55", 150.00)

    assert result["new_micros"] == 150_000_000
    assert result["previous_micros"] == 100_000_000


def test_update_campaign_budget_refuses_shared_budget(mock_client):
    shared_row = SimpleNamespace(
        campaign_budget=SimpleNamespace(
            id=999, amount_micros=100_000_000, explicitly_shared=True
        )
    )
    ga_service = MagicMock()
    ga_service.search.return_value = iter([shared_row])
    mock_client.get_service.return_value = ga_service

    with pytest.raises(AdsClientError) as exc:
        server._client.update_campaign_budget("1234567890", "55", 150.00)
    assert exc.value.code == "shared_budget_refused"


# ── Status mutation ──────────────────────────────────────────────────────────


def test_set_campaign_status_rejects_invalid_status(mock_client):
    with pytest.raises(AdsClientError) as exc:
        server._client.set_campaign_status("1234567890", "55", "REMOVED")
    assert exc.value.code == "invalid_status"


def test_set_campaign_status_rejects_garbage(mock_client):
    with pytest.raises(AdsClientError) as exc:
        server._client.set_campaign_status("1234567890", "55", "WHATEVER")
    assert exc.value.code == "invalid_status"


# ── Negative keywords ────────────────────────────────────────────────────────


def test_add_negative_keywords_batches(mock_client):
    campaign_service = MagicMock()
    campaign_service.campaign_path.return_value = "customers/1/campaigns/55"
    criterion_service = MagicMock()
    mutate_response = MagicMock()
    mutate_response.results = [
        MagicMock(resource_name=f"customers/1/campaignCriteria/55~{i}") for i in range(3)
    ]
    criterion_service.mutate_campaign_criteria.return_value = mutate_response

    def service_router(name):
        return campaign_service if name == "CampaignService" else criterion_service

    mock_client.get_service.side_effect = service_router

    # Each get_type call must return a fresh op so the loop produces distinct entries.
    mock_client.get_type.side_effect = lambda *a, **kw: MagicMock()
    enum_holder = MagicMock()
    enum_holder.BROAD = "BROAD"
    mock_client.enums.KeywordMatchTypeEnum.KeywordMatchType = enum_holder

    result = server._client.add_negative_keywords(
        "1234567890", "55", ["bad word", "another bad", "third"], match_type="BROAD"
    )

    assert result["count"] == 3
    assert result["match_type"] == "BROAD"
    assert result["keywords_added"] == ["bad word", "another bad", "third"]
    # Single mutate call for the batch
    assert criterion_service.mutate_campaign_criteria.call_count == 1
    sent_ops = criterion_service.mutate_campaign_criteria.call_args.kwargs["operations"]
    assert len(sent_ops) == 3


def test_add_negative_keywords_rejects_invalid_match_type(mock_client):
    with pytest.raises(AdsClientError) as exc:
        server._client.add_negative_keywords("1234567890", "55", ["a"], match_type="FUZZY")
    assert exc.value.code == "invalid_match_type"


def test_add_negative_keywords_rejects_empty_list(mock_client):
    with pytest.raises(AdsClientError) as exc:
        server._client.add_negative_keywords("1234567890", "55", [], match_type="BROAD")
    assert exc.value.code == "empty_keywords"


# ── AdsClientError handling at the tool layer ────────────────────────────────


@pytest.mark.asyncio
async def test_tool_returns_error_dict_not_exception(monkeypatch):
    def boom(*a, **kw):
        raise AdsClientError("simulated failure", code="test_failure")
    monkeypatch.setattr(server._client, "list_campaigns", boom)
    out = await server.get_campaigns(customer_id="1234567890")
    assert out["error"] == "test_failure"
    assert "simulated failure" in out["message"]


# ── Missing credentials: lazy, raises only on first real call ────────────────


def test_missing_credentials_does_not_raise_on_import():
    # If we got here, import succeeded with no env. Pass.
    wrapper = GoogleAdsClientWrapper(
        developer_token="", client_id="", client_secret="", refresh_token=""
    )
    # Build wrapper itself must not raise.
    assert wrapper._client is None


def test_missing_credentials_raises_on_first_call():
    wrapper = GoogleAdsClientWrapper(
        developer_token="", client_id="", client_secret="", refresh_token=""
    )
    with pytest.raises(AdsClientError) as exc:
        wrapper._ensure_client()
    assert exc.value.code == "missing_credentials"


# ── Status enum mapping ──────────────────────────────────────────────────────


def test_status_enum_mapping():
    t = Transformer()
    row = _make_campaign_row(status="PAUSED")
    assert t.campaign_from_row(row).status == CampaignStatus.PAUSED


def test_unknown_status_falls_back():
    t = Transformer()
    row = _make_campaign_row(status="WEIRD_STATE")
    assert t.campaign_from_row(row).status == CampaignStatus.UNKNOWN
