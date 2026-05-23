import os
from datetime import date, timedelta
from typing import Optional

from .base import BaseAdsClient, AdsClientError


VALID_MATCH_TYPES = {"EXACT", "PHRASE", "BROAD"}
MUTABLE_STATUSES = {"ENABLED", "PAUSED"}


def _clean_customer_id(cid: str) -> str:
    """Strip dashes and whitespace from a Google Ads customer ID."""
    return (cid or "").replace("-", "").replace(" ", "")


def _date_range(days: int) -> tuple[str, str]:
    end = date.today()
    start = end - timedelta(days=max(1, int(days)))
    return start.isoformat(), end.isoformat()


class GoogleAdsClientWrapper(BaseAdsClient):
    """Wraps google.ads.googleads.client.GoogleAdsClient with lazy auth."""

    name = "google_ads"

    def __init__(
        self,
        developer_token: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        refresh_token: Optional[str] = None,
        login_customer_id: Optional[str] = None,
        api_version: Optional[str] = None,
    ):
        self.developer_token = developer_token or os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", "")
        self.client_id = client_id or os.getenv("GOOGLE_ADS_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("GOOGLE_ADS_CLIENT_SECRET", "")
        self.refresh_token = refresh_token or os.getenv("GOOGLE_ADS_REFRESH_TOKEN", "")
        self.login_customer_id = _clean_customer_id(
            login_customer_id or os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "")
        )
        self.api_version = api_version or os.getenv("GOOGLE_ADS_API_VERSION") or None
        self._client = None

    # ── Auth ─────────────────────────────────────────────────────────────────

    def _ensure_client(self):
        if self._client is not None:
            return self._client

        missing = [
            name for name, val in [
                ("GOOGLE_ADS_DEVELOPER_TOKEN", self.developer_token),
                ("GOOGLE_ADS_CLIENT_ID", self.client_id),
                ("GOOGLE_ADS_CLIENT_SECRET", self.client_secret),
                ("GOOGLE_ADS_REFRESH_TOKEN", self.refresh_token),
            ] if not val
        ]
        if missing:
            raise AdsClientError(
                f"Google Ads credentials missing: {', '.join(missing)}",
                code="missing_credentials",
            )

        try:
            from google.ads.googleads.client import GoogleAdsClient
        except ImportError as e:
            raise AdsClientError(
                f"google-ads library not installed: {e}",
                code="missing_dependency",
            )

        creds = {
            "developer_token": self.developer_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "use_proto_plus": True,
        }
        if self.login_customer_id:
            creds["login_customer_id"] = self.login_customer_id

        if self.api_version:
            self._client = GoogleAdsClient.load_from_dict(creds, version=self.api_version)
        else:
            self._client = GoogleAdsClient.load_from_dict(creds)
        return self._client

    # ── Read paths ───────────────────────────────────────────────────────────

    def list_campaigns(self, customer_id: str) -> list[dict]:
        client = self._ensure_client()
        cid = _clean_customer_id(customer_id)
        ga_service = client.get_service("GoogleAdsService")
        query = """
            SELECT
              campaign.id,
              campaign.name,
              campaign.status,
              campaign.advertising_channel_type,
              campaign.bidding_strategy_type,
              campaign.start_date,
              campaign.end_date,
              campaign_budget.amount_micros,
              metrics.clicks,
              metrics.impressions,
              metrics.ctr,
              metrics.average_cpc,
              metrics.cost_micros,
              metrics.conversions,
              metrics.cost_per_conversion
            FROM campaign
            WHERE campaign.status != 'REMOVED'
            ORDER BY metrics.cost_micros DESC
        """
        stream = ga_service.search(customer_id=cid, query=query)
        return list(stream)

    def list_search_terms(
        self,
        customer_id: str,
        days: int = 30,
        campaign_id: Optional[str] = None,
    ) -> list[dict]:
        client = self._ensure_client()
        cid = _clean_customer_id(customer_id)
        ga_service = client.get_service("GoogleAdsService")
        start, end = _date_range(days)

        where_clauses = [
            f"segments.date BETWEEN '{start}' AND '{end}'",
            "metrics.impressions > 0",
        ]
        if campaign_id:
            where_clauses.append(f"campaign.id = {int(campaign_id)}")

        query = f"""
            SELECT
              search_term_view.search_term,
              metrics.clicks,
              metrics.impressions,
              metrics.ctr,
              metrics.average_cpc,
              metrics.cost_micros,
              metrics.conversions,
              campaign.id,
              campaign.name,
              ad_group.id
            FROM search_term_view
            WHERE {' AND '.join(where_clauses)}
            ORDER BY metrics.cost_micros DESC
            LIMIT 50
        """
        stream = ga_service.search(customer_id=cid, query=query)
        return list(stream)

    def get_campaign_budget(self, customer_id: str, campaign_id: str) -> dict:
        client = self._ensure_client()
        cid = _clean_customer_id(customer_id)
        ga_service = client.get_service("GoogleAdsService")
        # The campaign resource carries campaign_budget as an implicit join target;
        # selecting campaign_budget.* from campaign yields the linked budget row.
        # TODO: confirm against live API; fallback is to query `campaign_budget` directly
        # using the resource_name returned by `campaign.campaign_budget`.
        query = f"""
            SELECT
              campaign_budget.id,
              campaign_budget.amount_micros,
              campaign_budget.explicitly_shared
            FROM campaign
            WHERE campaign.id = {int(campaign_id)}
        """
        rows = list(ga_service.search(customer_id=cid, query=query))
        if not rows:
            raise AdsClientError(
                f"No budget found for campaign {campaign_id} on customer {cid}",
                code="budget_not_found",
            )
        return rows[0]

    # ── Mutate paths ─────────────────────────────────────────────────────────

    def update_campaign_budget(
        self,
        customer_id: str,
        campaign_id: str,
        daily_budget_usd: float,
    ) -> dict:
        client = self._ensure_client()
        cid = _clean_customer_id(customer_id)

        existing = self.get_campaign_budget(cid, campaign_id)
        budget_id = existing.campaign_budget.id
        previous_micros = existing.campaign_budget.amount_micros
        explicitly_shared = bool(getattr(existing.campaign_budget, "explicitly_shared", False))

        if explicitly_shared:
            raise AdsClientError(
                f"Budget {budget_id} is explicitly shared across campaigns. Refusing to mutate.",
                code="shared_budget_refused",
            )

        new_micros = int(round(float(daily_budget_usd) * 1_000_000))

        budget_service = client.get_service("CampaignBudgetService")
        operation = client.get_type("CampaignBudgetOperation")
        operation.update.resource_name = budget_service.campaign_budget_path(cid, budget_id)
        operation.update.amount_micros = new_micros

        from google.api_core import protobuf_helpers
        operation.update_mask.CopyFrom(
            protobuf_helpers.field_mask(None, operation.update._pb)
        )

        response = budget_service.mutate_campaign_budgets(
            customer_id=cid,
            operations=[operation],
        )
        return {
            "budget_id": str(budget_id),
            "previous_micros": int(previous_micros) if previous_micros is not None else None,
            "new_micros": new_micros,
            "resource_name": response.results[0].resource_name if response.results else None,
        }

    def set_campaign_status(self, customer_id: str, campaign_id: str, status: str) -> dict:
        status = (status or "").upper()
        if status not in MUTABLE_STATUSES:
            raise AdsClientError(
                f"status must be one of {sorted(MUTABLE_STATUSES)}. Got '{status}'.",
                code="invalid_status",
            )
        client = self._ensure_client()
        cid = _clean_customer_id(customer_id)
        campaign_service = client.get_service("CampaignService")
        status_enum = client.enums.CampaignStatusEnum.CampaignStatus

        operation = client.get_type("CampaignOperation")
        operation.update.resource_name = campaign_service.campaign_path(cid, campaign_id)
        operation.update.status = getattr(status_enum, status)

        from google.api_core import protobuf_helpers
        operation.update_mask.CopyFrom(
            protobuf_helpers.field_mask(None, operation.update._pb)
        )

        response = campaign_service.mutate_campaigns(
            customer_id=cid,
            operations=[operation],
        )
        return {
            "campaign_id": str(campaign_id),
            "new_status": status,
            "resource_name": response.results[0].resource_name if response.results else None,
        }

    def add_negative_keywords(
        self,
        customer_id: str,
        campaign_id: str,
        keywords: list[str],
        match_type: str = "BROAD",
    ) -> dict:
        match_type = (match_type or "BROAD").upper()
        if match_type not in VALID_MATCH_TYPES:
            raise AdsClientError(
                f"match_type must be one of {sorted(VALID_MATCH_TYPES)}. Got '{match_type}'.",
                code="invalid_match_type",
            )
        keywords = [k for k in (keywords or []) if k and k.strip()]
        if not keywords:
            raise AdsClientError("keywords list is empty", code="empty_keywords")

        client = self._ensure_client()
        cid = _clean_customer_id(customer_id)
        campaign_service = client.get_service("CampaignService")
        criterion_service = client.get_service("CampaignCriterionService")
        match_enum = client.enums.KeywordMatchTypeEnum.KeywordMatchType

        operations = []
        campaign_resource = campaign_service.campaign_path(cid, campaign_id)
        for kw in keywords:
            op = client.get_type("CampaignCriterionOperation")
            op.create.campaign = campaign_resource
            op.create.negative = True
            op.create.keyword.text = kw.strip()
            op.create.keyword.match_type = getattr(match_enum, match_type)
            operations.append(op)

        response = criterion_service.mutate_campaign_criteria(
            customer_id=cid,
            operations=operations,
        )
        return {
            "campaign_id": str(campaign_id),
            "match_type": match_type,
            "keywords_added": keywords,
            "count": len(response.results),
            "resource_names": [r.resource_name for r in response.results],
        }
