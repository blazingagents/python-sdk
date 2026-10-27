from __future__ import annotations

from collections.abc import Mapping

from ._models import SpendingLimitResponse, TenantSettings
from ._transport import (
    OMITTED,
    AsyncTransport,
    _Omitted,
    _Request,
    decode_model,
    wire_fields,
)
from ._types import (
    SpendingLimitInput,
    Timeout,
)
from ._wire import spending_limit_body


class AsyncTenantResource:
    async def get_spending_limit(
        self,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> SpendingLimitResponse:
        """Fetch the tenant model spending limit using tenant authority."""
        return await self._transport.request(
            _Request(
                "GET",
                "/v1/tenant/spending-limit",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(SpendingLimitResponse),
        )

    async def update_spending_limit(
        self,
        *,
        spending_limit: SpendingLimitInput | None,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> SpendingLimitResponse:
        """Set or disable the tenant model spending limit using tenant authority."""
        return await self._transport.request(
            _Request(
                "PUT",
                "/v1/tenant/spending-limit",
                json_body=spending_limit_body(spending_limit),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(SpendingLimitResponse),
        )

    def __init__(self, transport: AsyncTransport) -> None:
        """Bind Tenant settings operations to the transport.

        Args:
            transport: Transport used for requests.
        """
        self._transport = transport

    async def get(
        self,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> TenantSettings:
        """Fetch the requested Tenant settings.

        Args:
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Tenant settings.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "GET",
                "/v1/tenant",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(TenantSettings),
        )

    async def update(
        self,
        *,
        name: str | _Omitted = OMITTED,
        monetization_enabled: bool | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> TenantSettings:
        """Update the provided Tenant settings fields.

        Args:
            name: Tenant display name, 1 to 80 characters.
            monetization_enabled: Bill usage to your end users through your
                merchant account. Turning it off drops usage events the merchant
                has not accepted yet.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            Tenant settings.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "PATCH",
                "/v1/tenant",
                json_body=wire_fields(
                    name=name, monetization_enabled=monetization_enabled
                ),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            decode_model(TenantSettings),
        )
