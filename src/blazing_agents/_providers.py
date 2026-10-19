from __future__ import annotations

from collections.abc import Mapping

from ._models import Provider, ProviderModels, Providers, ThinkingLevels
from ._transport import (
    OMITTED,
    AsyncTransport,
    _Omitted,
    _Request,
    decode_model,
    decode_none,
    path_segment,
    wire_fields,
)
from ._types import (
    ProviderType,
    Timeout,
)


def _provider_body(
    *,
    provider_type: ProviderType,
    api_key: str,
    model: str | _Omitted,
    name: str | _Omitted,
    base_url: str | None | _Omitted,
) -> dict[str, object]:
    """Build the provider request body, omitting unspecified fields."""
    body: dict[str, object] = {
        "providerType": provider_type,
        "apiKey": api_key,
    }
    body |= wire_fields(name=name, base_url=base_url, model=model)
    return body


def _provider_update_body(
    name: str | _Omitted,
) -> dict[str, object]:
    """Build the provider update request body, omitting unspecified fields."""
    return {} if isinstance(name, _Omitted) else {"name": name}


def _provider_path(provider_id: str) -> str:
    """Build the encoded provider endpoint path."""
    return f"/v1/providers/{path_segment('provider_id', provider_id)}"


class AsyncProvidersResource:
    def __init__(self, transport: AsyncTransport) -> None:
        """Bind Provider operations to the transport.

        Args:
            transport: Transport used for requests.
        """
        self._transport = transport

    async def create(
        self,
        *,
        name: str,
        provider_type: ProviderType,
        api_key: str,
        base_url: str | None | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Provider:
        """Create a Provider.

        Args:
            name: Provider display name, unique within the tenant.
            provider_type: Provider API type.
            api_key: The vendor API key. It is stored encrypted, never returned,
                and cannot be changed later.
            base_url: Endpoint override. Required for custom, not accepted for
                vercel_ai_gateway, and optional otherwise. Cannot be changed later.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Provider details.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "POST",
                "/v1/providers",
                json_body=_provider_body(
                    provider_type=provider_type,
                    api_key=api_key,
                    model=OMITTED,
                    name=name,
                    base_url=base_url,
                ),
                extra_headers=extra_headers,
                timeout=timeout,
                sensitive_values=(api_key,),
            ),
            decode_model(Provider),
        )

    async def list(
        self,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Providers:
        """Fetch one page of Provider records.

        Args:
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Available Providers.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "GET",
                "/v1/providers",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(Providers),
        )

    async def get(
        self,
        provider_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Provider:
        """Fetch the requested Provider.

        Args:
            provider_id: Provider identifier. Supply with model when configuring an
                Agent.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Provider details.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "GET",
                _provider_path(provider_id),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(Provider),
        )

    async def list_models(
        self,
        provider_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ProviderModels:
        """Fetch available models for a Provider.

        Args:
            provider_id: Provider identifier. Supply with model when configuring an
                Agent.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Models advertised by the Provider.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "GET",
                f"{_provider_path(provider_id)}/models",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(ProviderModels),
        )

    async def get_thinking_levels(
        self,
        provider_id: str,
        *,
        model: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> ThinkingLevels:
        """Fetch supported thinking levels for a model.

        Args:
            provider_id: Provider identifier. Supply with model when configuring an
                Agent.
            model: Provider model identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Thinking levels supported by the selected model.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "GET",
                f"{_provider_path(provider_id)}/thinking-levels",
                query={"model": model},
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(ThinkingLevels),
        )

    async def update(
        self,
        provider_id: str,
        *,
        name: str | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Provider:
        """Update the provided Provider fields.

        Args:
            provider_id: Provider identifier. Supply with model when configuring an
                Agent.
            name: Provider display name, unique within the tenant.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Requested Provider details.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "PATCH",
                _provider_path(provider_id),
                json_body=_provider_update_body(name),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(Provider),
        )

    async def delete(
        self,
        provider_id: str,
        *,
        confirm_snapshot_invalidation: bool = False,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> None:
        """Delete the requested Provider.

        Args:
            provider_id: Provider identifier. Supply with model when configuring an
                Agent.
            confirm_snapshot_invalidation: Explicit consent to invalidate dependent
                snapshots.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "DELETE",
                _provider_path(provider_id),
                query=(
                    {"confirmSnapshotInvalidation": "true"}
                    if confirm_snapshot_invalidation
                    else {}
                ),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_none,
        )
