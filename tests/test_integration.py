"""Live integration smoke test. Skipped unless GOOGLE_ADS_DEVELOPER_TOKEN is set."""
import os
import pytest

from gadschain.clients.google_ads import GoogleAdsClientWrapper
from gadschain.core.transformer import Transformer
from gadschain.models.campaign import CampaignList

# Franka Pizzeria customer ID
FRANKA_CUSTOMER_ID = "6797670184"

pytestmark = pytest.mark.skipif(
    not os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN"),
    reason="GOOGLE_ADS_DEVELOPER_TOKEN not set — skipping live integration test",
)


def test_list_campaigns_against_franka():
    wrapper = GoogleAdsClientWrapper()
    t = Transformer()

    rows = wrapper.list_campaigns(FRANKA_CUSTOMER_ID)
    campaigns = [t.campaign_from_row(r) for r in rows]
    result = CampaignList(
        customer_id=FRANKA_CUSTOMER_ID,
        campaigns=campaigns,
        total_count=len(campaigns),
    )

    # Schema is the only hard contract — Franka could have zero campaigns at any point.
    assert isinstance(result, CampaignList)
    assert result.customer_id == FRANKA_CUSTOMER_ID
    assert result.total_count == len(result.campaigns)

    print(f"\n=== Franka Pizzeria ({FRANKA_CUSTOMER_ID}) ===")
    print(f"Total campaigns: {result.total_count}")
    for c in result.campaigns:
        spend = f"${c.cost_dollars:,.2f}" if c.cost_dollars is not None else "—"
        budget = f"${c.daily_budget_dollars:,.2f}/day" if c.daily_budget_dollars is not None else "—"
        print(f"  [{c.status.value:>8}] {c.name!r:40} budget={budget:>14} spend={spend}")
