"""Provider-neutral, non-executing adapter protocols.

Concrete providers are intentionally absent.  A future manual integration must
implement these protocols and produce the corresponding validated receipts.
"""

from __future__ import annotations

from typing import Any, Protocol


class SearchDemandProvider(Protocol):
    provider_id: str
    def acquire(self, query_context: str, market: str, locale: str) -> list[dict[str, Any]]: ...


class SearchEvidenceProvider(Protocol):
    provider_id: str
    def retrieve(self, query: str) -> list[dict[str, Any]]: ...


class AffiliateProvider(Protocol):
    provider_id: str
    def discover(self, topic_packet_digest: str) -> list[dict[str, Any]]: ...


class AnalyticsProvider(Protocol):
    provider_id: str
    property_id: str
    def observe(self, post_id: str, window: dict[str, str]) -> dict[str, Any]: ...


class PublicationAdapter(Protocol):
    adapter_id: str
    def execute_with_existing_authority(self, publication_candidate: dict[str, Any]) -> dict[str, Any]: ...


class ImageMaterializer(Protocol):
    provider_id: str
    def materialize_candidate(self, validated_plan: dict[str, Any]) -> dict[str, Any]: ...
