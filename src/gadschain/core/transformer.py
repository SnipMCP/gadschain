"""Map google-ads response rows into Pydantic models. Missing fields → None."""

from typing import Any, Optional

from ..models.campaign import (
    Campaign,
    CampaignStatus,
    SearchTerm,
    CampaignBudgetInfo,
    BudgetUpdateResult,
    StatusChangeResult,
    NegativeKeywordAddResult,
)


def _g(obj: Any, *path: str, default: Any = None) -> Any:
    """Safely walk nested attributes on a protobuf row. Returns default if any hop is None or absent."""
    cur = obj
    for p in path:
        if cur is None:
            return default
        cur = getattr(cur, p, None)
    return cur if cur is not None else default


def _status_from_enum(status_value: Any) -> CampaignStatus:
    if status_value is None:
        return CampaignStatus.UNKNOWN
    name = getattr(status_value, "name", None) or str(status_value)
    name = name.upper()
    if name == "ENABLED":
        return CampaignStatus.ENABLED
    if name == "PAUSED":
        return CampaignStatus.PAUSED
    if name == "REMOVED":
        return CampaignStatus.REMOVED
    return CampaignStatus.UNKNOWN


def _micros_to_dollars(micros: Optional[int]) -> Optional[float]:
    if micros is None:
        return None
    try:
        return round(int(micros) / 1_000_000, 2)
    except (TypeError, ValueError):
        return None


def _ctr_to_percent(ctr: Optional[float]) -> Optional[float]:
    if ctr is None:
        return None
    try:
        return round(float(ctr) * 100, 4)
    except (TypeError, ValueError):
        return None


def _enum_name(val: Any) -> Optional[str]:
    if val is None:
        return None
    return getattr(val, "name", None) or str(val)


class Transformer:
    def campaign_from_row(self, row: Any) -> Campaign:
        campaign_id = _g(row, "campaign", "id")
        cost_micros = _g(row, "metrics", "cost_micros")
        avg_cpc_micros = _g(row, "metrics", "average_cpc")
        budget_micros = _g(row, "campaign_budget", "amount_micros")
        cost_per_conv = _g(row, "metrics", "cost_per_conversion")

        return Campaign(
            id=str(campaign_id) if campaign_id is not None else "",
            name=_g(row, "campaign", "name", default="") or "",
            status=_status_from_enum(_g(row, "campaign", "status")),
            advertising_channel_type=_enum_name(_g(row, "campaign", "advertising_channel_type")),
            daily_budget_micros=int(budget_micros) if budget_micros is not None else None,
            daily_budget_dollars=_micros_to_dollars(budget_micros),
            bidding_strategy=_enum_name(_g(row, "campaign", "bidding_strategy_type")),
            start_date=_g(row, "campaign", "start_date"),
            end_date=_g(row, "campaign", "end_date"),
            impressions=int(_g(row, "metrics", "impressions") or 0) or None,
            clicks=int(_g(row, "metrics", "clicks") or 0) or None,
            ctr_percent=_ctr_to_percent(_g(row, "metrics", "ctr")),
            average_cpc_micros=int(avg_cpc_micros) if avg_cpc_micros is not None else None,
            average_cpc_dollars=_micros_to_dollars(avg_cpc_micros),
            cost_micros=int(cost_micros) if cost_micros is not None else None,
            cost_dollars=_micros_to_dollars(cost_micros),
            conversions=float(_g(row, "metrics", "conversions") or 0) or None,
            # cost_per_conversion is reported by Google Ads in raw currency units, not micros
            cost_per_conversion_dollars=round(float(cost_per_conv), 2) if cost_per_conv else None,
        )

    def search_term_from_row(self, row: Any) -> SearchTerm:
        cost_micros = _g(row, "metrics", "cost_micros")
        avg_cpc_micros = _g(row, "metrics", "average_cpc")
        campaign_id = _g(row, "campaign", "id")
        ad_group_id = _g(row, "ad_group", "id")

        return SearchTerm(
            campaign_id=str(campaign_id) if campaign_id is not None else "",
            campaign_name=_g(row, "campaign", "name"),
            ad_group_id=str(ad_group_id) if ad_group_id is not None else None,
            search_term=_g(row, "search_term_view", "search_term", default="") or "",
            impressions=int(_g(row, "metrics", "impressions") or 0) or None,
            clicks=int(_g(row, "metrics", "clicks") or 0) or None,
            ctr_percent=_ctr_to_percent(_g(row, "metrics", "ctr")),
            average_cpc_micros=int(avg_cpc_micros) if avg_cpc_micros is not None else None,
            average_cpc_dollars=_micros_to_dollars(avg_cpc_micros),
            cost_micros=int(cost_micros) if cost_micros is not None else None,
            cost_dollars=_micros_to_dollars(cost_micros),
            conversions=float(_g(row, "metrics", "conversions") or 0) or None,
        )

    def budget_info_from_row(self, customer_id: str, campaign_id: str, row: Any) -> CampaignBudgetInfo:
        amt = _g(row, "campaign_budget", "amount_micros")
        return CampaignBudgetInfo(
            customer_id=str(customer_id),
            campaign_id=str(campaign_id),
            budget_id=str(_g(row, "campaign_budget", "id") or ""),
            amount_micros=int(amt) if amt is not None else None,
            amount_dollars=_micros_to_dollars(amt),
            explicitly_shared=bool(_g(row, "campaign_budget", "explicitly_shared") or False),
        )

    def budget_result(
        self,
        customer_id: str,
        campaign_id: str,
        previous_micros: Optional[int],
        new_micros: int,
        success: bool = True,
        message: Optional[str] = None,
    ) -> BudgetUpdateResult:
        return BudgetUpdateResult(
            customer_id=str(customer_id),
            campaign_id=str(campaign_id),
            previous_budget_micros=previous_micros,
            previous_budget_dollars=_micros_to_dollars(previous_micros),
            new_budget_micros=new_micros,
            new_budget_dollars=_micros_to_dollars(new_micros) or 0.0,
            success=success,
            message=message,
        )

    def status_result(
        self,
        customer_id: str,
        campaign_id: str,
        new_status: str,
        previous_status: Optional[str] = None,
        success: bool = True,
        message: Optional[str] = None,
    ) -> StatusChangeResult:
        return StatusChangeResult(
            customer_id=str(customer_id),
            campaign_id=str(campaign_id),
            previous_status=_status_from_enum(previous_status) if previous_status else None,
            new_status=_status_from_enum(new_status),
            success=success,
            message=message,
        )

    def negative_keyword_result(
        self,
        customer_id: str,
        campaign_id: str,
        keywords: list[str],
        match_type: str,
        count: int,
        success: bool = True,
        message: Optional[str] = None,
    ) -> NegativeKeywordAddResult:
        return NegativeKeywordAddResult(
            customer_id=str(customer_id),
            campaign_id=str(campaign_id),
            keywords_added=keywords,
            match_type=match_type,
            count=count,
            success=success,
            message=message,
        )
