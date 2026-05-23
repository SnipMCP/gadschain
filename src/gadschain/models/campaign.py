from pydantic import BaseModel
from typing import Optional
from enum import Enum


class CampaignStatus(str, Enum):
    ENABLED = "enabled"
    PAUSED = "paused"
    REMOVED = "removed"
    UNKNOWN = "unknown"


class Campaign(BaseModel):
    id: str
    name: str
    status: CampaignStatus
    advertising_channel_type: Optional[str] = None
    daily_budget_micros: Optional[int] = None
    daily_budget_dollars: Optional[float] = None
    bidding_strategy: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    impressions: Optional[int] = None
    clicks: Optional[int] = None
    ctr_percent: Optional[float] = None
    average_cpc_micros: Optional[int] = None
    average_cpc_dollars: Optional[float] = None
    cost_micros: Optional[int] = None
    cost_dollars: Optional[float] = None
    conversions: Optional[float] = None
    cost_per_conversion_dollars: Optional[float] = None


class CampaignList(BaseModel):
    customer_id: str
    campaigns: list[Campaign]
    total_count: int


class SearchTerm(BaseModel):
    campaign_id: str
    campaign_name: Optional[str] = None
    ad_group_id: Optional[str] = None
    search_term: str
    impressions: Optional[int] = None
    clicks: Optional[int] = None
    ctr_percent: Optional[float] = None
    average_cpc_micros: Optional[int] = None
    average_cpc_dollars: Optional[float] = None
    cost_micros: Optional[int] = None
    cost_dollars: Optional[float] = None
    conversions: Optional[float] = None


class SearchTermList(BaseModel):
    customer_id: str
    terms: list[SearchTerm]
    total_count: int
    date_range: Optional[str] = None


class CampaignBudgetInfo(BaseModel):
    customer_id: str
    campaign_id: str
    budget_id: Optional[str] = None
    amount_micros: Optional[int] = None
    amount_dollars: Optional[float] = None
    explicitly_shared: Optional[bool] = None


class BudgetUpdateResult(BaseModel):
    customer_id: str
    campaign_id: str
    previous_budget_micros: Optional[int] = None
    previous_budget_dollars: Optional[float] = None
    new_budget_micros: int
    new_budget_dollars: float
    success: bool
    message: Optional[str] = None


class StatusChangeResult(BaseModel):
    customer_id: str
    campaign_id: str
    previous_status: Optional[CampaignStatus] = None
    new_status: CampaignStatus
    success: bool
    message: Optional[str] = None


class NegativeKeywordAddResult(BaseModel):
    customer_id: str
    campaign_id: str
    keywords_added: list[str]
    match_type: str
    count: int
    success: bool
    message: Optional[str] = None
