from abc import ABC, abstractmethod
from typing import Optional


class AdsClientError(Exception):
    def __init__(self, message: str, code: Optional[str] = None):
        super().__init__(message)
        self.code = code


class BaseAdsClient(ABC):
    name: str = "base"

    @abstractmethod
    def list_campaigns(self, customer_id: str) -> list[dict]:
        ...

    @abstractmethod
    def list_search_terms(self, customer_id: str, days: int, campaign_id: Optional[str] = None) -> list[dict]:
        ...

    @abstractmethod
    def get_campaign_budget(self, customer_id: str, campaign_id: str) -> dict:
        ...

    @abstractmethod
    def update_campaign_budget(self, customer_id: str, campaign_id: str, daily_budget_usd: float) -> dict:
        ...

    @abstractmethod
    def set_campaign_status(self, customer_id: str, campaign_id: str, status: str) -> dict:
        ...

    @abstractmethod
    def add_negative_keywords(
        self,
        customer_id: str,
        campaign_id: str,
        keywords: list[str],
        match_type: str = "BROAD",
    ) -> dict:
        ...
