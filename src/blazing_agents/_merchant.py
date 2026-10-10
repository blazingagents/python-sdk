from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Mapping

from ._chat import path_segment
from ._models import (
    MerchantBindingResponse,
    MerchantBindingsPage,
    MerchantConnectionResponse,
    MerchantCustomerBinding,
    MerchantUsageEvent,
    MerchantUsageEventResponse,
    MerchantUsageEventsPage,
    MerchantUsageSummaryResponse,
)
from ._transport import OMITTED, AsyncTransport, SyncTransport, _Omitted, _Request
from ._types import (
    MerchantConnectionStatus,
    MerchantEnvironment,
    MerchantGuardInput,
    MerchantProvider,
    MerchantUsageEventStatus,
    Timeout,
)

_CONNECTION_PATH = "/v1/merchant-connection"
_BINDINGS_PATH = "/v1/merchant-connection/bindings"
_EVENTS_PATH = "/v1/merchant-usage-events"


def _guard_body(guard: MerchantGuardInput) -> dict[str, object]:
    """Convert a guard input to its wire shape."""
    return {
        "enabled": guard["enabled"],
        "productIds": guard["product_ids"],
        "meterId": guard["meter_id"],
    }


def _query(*fields: tuple[str, str | int | _Omitted]) -> dict[str, str | int]:
    """Build a query, omitting unspecified filters."""
    return {
        wire_name: value
        for wire_name, value in fields
        if not isinstance(value, _Omitted)
    }


def _present(*fields: tuple[str, object]) -> dict[str, object]:
    """Keep the fields whose value is not OMITTED."""
    return {
        wire_name: value
        for wire_name, value in fields
        if not isinstance(value, _Omitted)
    }


class MerchantConnectionResource:
    def __init__(self, transport: SyncTransport) -> None:
        """Bind merchant connection operations to the transport.

        Args:
            transport: Transport used for requests.
        """
        self._transport = transport

    def get(
        self,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> MerchantConnectionResponse:
        """Fetch the Tenant's merchant connection.

        Args:
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            The connection, or None when the Tenant has none.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return self._transport.request(
            _Request(
                "GET",
                _CONNECTION_PATH,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            MerchantConnectionResponse,
        )

    def create(
        self,
        *,
        provider: MerchantProvider,
        environment: MerchantEnvironment,
        credential: str,
        guard: MerchantGuardInput | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> MerchantConnectionResponse:
        """Connect the Tenant's Polar or Dodo account.

        The credential is write-only. Responses show only its last characters.

        Args:
            provider: Merchant provider.
            environment: Provider environment.
            credential: Provider access token.
            guard: Optional pre-Turn plan or balance check.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            The created connection.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        json_body = _present(
            ("provider", provider),
            ("environment", environment),
            ("credential", credential),
        )
        if not isinstance(guard, _Omitted):
            json_body["guard"] = _guard_body(guard)
        return self._transport.request(
            _Request(
                "POST",
                _CONNECTION_PATH,
                json_body=json_body,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            MerchantConnectionResponse,
        )

    def update(
        self,
        *,
        credential: str | _Omitted = OMITTED,
        status: MerchantConnectionStatus | _Omitted = OMITTED,
        guard: MerchantGuardInput | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> MerchantConnectionResponse:
        """Update the merchant connection.

        Omitted fields keep their current values.

        Args:
            credential: Replacement provider access token.
            status: Connection status. disconnected pauses deliveries.
            guard: Replacement pre-Turn plan or balance check.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            The updated connection.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        json_body = _present(("credential", credential), ("status", status))
        if not isinstance(guard, _Omitted):
            json_body["guard"] = _guard_body(guard)
        return self._transport.request(
            _Request(
                "PATCH",
                _CONNECTION_PATH,
                json_body=json_body,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            MerchantConnectionResponse,
        )

    def retire(
        self,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> None:
        """Retire the merchant connection and stop deliveries.

        Args:
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return self._transport.request(
            _Request(
                "DELETE",
                _CONNECTION_PATH,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            None,
        )


class MerchantBindingsResource:
    def __init__(self, transport: SyncTransport) -> None:
        """Bind merchant customer binding operations to the transport.

        Args:
            transport: Transport used for requests.
        """
        self._transport = transport

    def list(
        self,
        *,
        user_id: str | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> MerchantBindingsPage:
        """Fetch one page of end-user to provider customer bindings.

        Args:
            user_id: Exact end-user ID filter.
            cursor: Continuation cursor from a previous page.
            limit: Maximum number of items per page, 1 to 200.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            One page of bindings and its continuation cursor.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return self._transport.request(
            _Request(
                "GET",
                _BINDINGS_PATH,
                query=_query(("userId", user_id), ("cursor", cursor), ("limit", limit)),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            MerchantBindingsPage,
        )

    def iter(
        self,
        *,
        user_id: str | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Iterator[MerchantCustomerBinding]:
        """Iterate bindings across all pages.

        Pages are fetched lazily. limit controls each page, not the total.

        Args:
            user_id: Exact end-user ID filter.
            cursor: Continuation cursor from a previous page.
            limit: Maximum number of items per page, 1 to 200.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Yields:
            MerchantCustomerBinding records in server order.
        """
        next_cursor = cursor
        while True:
            page = self.list(
                user_id=user_id,
                cursor=next_cursor,
                limit=limit,
                extra_headers=extra_headers,
                timeout=timeout,
            )
            yield from page.bindings
            if page.next_cursor is None:
                return
            next_cursor = page.next_cursor

    def put(
        self,
        user_id: str,
        *,
        customer_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> MerchantBindingResponse:
        """Link an end user to a provider customer.

        The API checks that the customer exists at the provider before saving.

        Args:
            user_id: End-user ID your Turns send.
            customer_id: Provider customer ID.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            The saved binding.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return self._transport.request(
            _Request(
                "PUT",
                f"{_BINDINGS_PATH}/{path_segment('user_id', user_id)}",
                json_body={"customerId": customer_id},
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            MerchantBindingResponse,
        )

    def delete(
        self,
        user_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> None:
        """Remove an end user's provider customer binding.

        Args:
            user_id: End-user ID.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return self._transport.request(
            _Request(
                "DELETE",
                f"{_BINDINGS_PATH}/{path_segment('user_id', user_id)}",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            None,
        )


class MerchantUsageEventsResource:
    def __init__(self, transport: SyncTransport) -> None:
        """Bind merchant usage event operations to the transport.

        Args:
            transport: Transport used for requests.
        """
        self._transport = transport

    def list(
        self,
        *,
        status: MerchantUsageEventStatus | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> MerchantUsageEventsPage:
        """Fetch one page of usage events sent to the merchant provider.

        Args:
            status: Status filter.
            cursor: Continuation cursor from a previous page.
            limit: Maximum number of items per page, 1 to 200.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            One page of events and its continuation cursor.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return self._transport.request(
            _Request(
                "GET",
                _EVENTS_PATH,
                query=_query(("status", status), ("cursor", cursor), ("limit", limit)),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            MerchantUsageEventsPage,
        )

    def iter(
        self,
        *,
        status: MerchantUsageEventStatus | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> Iterator[MerchantUsageEvent]:
        """Iterate usage events across all pages.

        Pages are fetched lazily. limit controls each page, not the total.

        Args:
            status: Status filter.
            cursor: Continuation cursor from a previous page.
            limit: Maximum number of items per page, 1 to 200.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Yields:
            MerchantUsageEvent records in server order.
        """
        next_cursor = cursor
        while True:
            page = self.list(
                status=status,
                cursor=next_cursor,
                limit=limit,
                extra_headers=extra_headers,
                timeout=timeout,
            )
            yield from page.events
            if page.next_cursor is None:
                return
            next_cursor = page.next_cursor

    def get(
        self,
        event_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> MerchantUsageEventResponse:
        """Fetch one usage event.

        Args:
            event_id: Merchant usage event identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            The event and its next_action.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return self._transport.request(
            _Request(
                "GET",
                f"{_EVENTS_PATH}/{path_segment('event_id', event_id)}",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            MerchantUsageEventResponse,
        )

    def summary(
        self,
        *,
        days: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> MerchantUsageSummaryResponse:
        """Fetch delivery health: status counts and a daily window.

        Args:
            days: UTC days in the daily window, 1 to 90. Defaults to 14.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            All-time status counts and per-day delivery totals.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return self._transport.request(
            _Request(
                "GET",
                f"{_EVENTS_PATH}/summary",
                query=_query(("days", days)),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            MerchantUsageSummaryResponse,
        )

    def retry(
        self,
        event_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> MerchantUsageEventResponse:
        """Send a failed or uncertain event again.

        Args:
            event_id: Merchant usage event identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            The event after the request.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return self._transport.request(
            _Request(
                "POST",
                f"{_EVENTS_PATH}/{path_segment('event_id', event_id)}/retry",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            MerchantUsageEventResponse,
        )

    def release(
        self,
        event_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> MerchantUsageEventResponse:
        """Send an unmapped event after you bind its end user.

        Args:
            event_id: Merchant usage event identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            The event after the request.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return self._transport.request(
            _Request(
                "POST",
                f"{_EVENTS_PATH}/{path_segment('event_id', event_id)}/release",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            MerchantUsageEventResponse,
        )

    def discard(
        self,
        event_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> MerchantUsageEventResponse:
        """Stop delivering an event.

        Args:
            event_id: Merchant usage event identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            The event after the request.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return self._transport.request(
            _Request(
                "POST",
                f"{_EVENTS_PATH}/{path_segment('event_id', event_id)}/discard",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            MerchantUsageEventResponse,
        )


class AsyncMerchantConnectionResource:
    def __init__(self, transport: AsyncTransport) -> None:
        """Bind merchant connection operations to the transport.

        Args:
            transport: Transport used for requests.
        """
        self._transport = transport

    async def get(
        self,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> MerchantConnectionResponse:
        """Fetch the Tenant's merchant connection.

        Args:
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            The connection, or None when the Tenant has none.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "GET",
                _CONNECTION_PATH,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            MerchantConnectionResponse,
        )

    async def create(
        self,
        *,
        provider: MerchantProvider,
        environment: MerchantEnvironment,
        credential: str,
        guard: MerchantGuardInput | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> MerchantConnectionResponse:
        """Connect the Tenant's Polar or Dodo account.

        The credential is write-only. Responses show only its last characters.

        Args:
            provider: Merchant provider.
            environment: Provider environment.
            credential: Provider access token.
            guard: Optional pre-Turn plan or balance check.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            The created connection.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        json_body = _present(
            ("provider", provider),
            ("environment", environment),
            ("credential", credential),
        )
        if not isinstance(guard, _Omitted):
            json_body["guard"] = _guard_body(guard)
        return await self._transport.request(
            _Request(
                "POST",
                _CONNECTION_PATH,
                json_body=json_body,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            MerchantConnectionResponse,
        )

    async def update(
        self,
        *,
        credential: str | _Omitted = OMITTED,
        status: MerchantConnectionStatus | _Omitted = OMITTED,
        guard: MerchantGuardInput | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> MerchantConnectionResponse:
        """Update the merchant connection.

        Omitted fields keep their current values.

        Args:
            credential: Replacement provider access token.
            status: Connection status. disconnected pauses deliveries.
            guard: Replacement pre-Turn plan or balance check.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            The updated connection.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        json_body = _present(("credential", credential), ("status", status))
        if not isinstance(guard, _Omitted):
            json_body["guard"] = _guard_body(guard)
        return await self._transport.request(
            _Request(
                "PATCH",
                _CONNECTION_PATH,
                json_body=json_body,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            MerchantConnectionResponse,
        )

    async def retire(
        self,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> None:
        """Retire the merchant connection and stop deliveries.

        Args:
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
                _CONNECTION_PATH,
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            None,
        )


class AsyncMerchantBindingsResource:
    def __init__(self, transport: AsyncTransport) -> None:
        """Bind merchant customer binding operations to the transport.

        Args:
            transport: Transport used for requests.
        """
        self._transport = transport

    async def list(
        self,
        *,
        user_id: str | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> MerchantBindingsPage:
        """Fetch one page of end-user to provider customer bindings.

        Args:
            user_id: Exact end-user ID filter.
            cursor: Continuation cursor from a previous page.
            limit: Maximum number of items per page, 1 to 200.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            One page of bindings and its continuation cursor.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "GET",
                _BINDINGS_PATH,
                query=_query(("userId", user_id), ("cursor", cursor), ("limit", limit)),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            MerchantBindingsPage,
        )

    async def iter(
        self,
        *,
        user_id: str | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> AsyncIterator[MerchantCustomerBinding]:
        """Iterate bindings across all pages.

        Pages are fetched lazily. limit controls each page, not the total.

        Args:
            user_id: Exact end-user ID filter.
            cursor: Continuation cursor from a previous page.
            limit: Maximum number of items per page, 1 to 200.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Yields:
            MerchantCustomerBinding records in server order.
        """
        next_cursor = cursor
        while True:
            page = await self.list(
                user_id=user_id,
                cursor=next_cursor,
                limit=limit,
                extra_headers=extra_headers,
                timeout=timeout,
            )
            for item in page.bindings:
                yield item
            if page.next_cursor is None:
                return
            next_cursor = page.next_cursor

    async def put(
        self,
        user_id: str,
        *,
        customer_id: str,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> MerchantBindingResponse:
        """Link an end user to a provider customer.

        The API checks that the customer exists at the provider before saving.

        Args:
            user_id: End-user ID your Turns send.
            customer_id: Provider customer ID.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            The saved binding.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "PUT",
                f"{_BINDINGS_PATH}/{path_segment('user_id', user_id)}",
                json_body={"customerId": customer_id},
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            MerchantBindingResponse,
        )

    async def delete(
        self,
        user_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> None:
        """Remove an end user's provider customer binding.

        Args:
            user_id: End-user ID.
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
                f"{_BINDINGS_PATH}/{path_segment('user_id', user_id)}",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            None,
        )


class AsyncMerchantUsageEventsResource:
    def __init__(self, transport: AsyncTransport) -> None:
        """Bind merchant usage event operations to the transport.

        Args:
            transport: Transport used for requests.
        """
        self._transport = transport

    async def list(
        self,
        *,
        status: MerchantUsageEventStatus | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> MerchantUsageEventsPage:
        """Fetch one page of usage events sent to the merchant provider.

        Args:
            status: Status filter.
            cursor: Continuation cursor from a previous page.
            limit: Maximum number of items per page, 1 to 200.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            One page of events and its continuation cursor.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "GET",
                _EVENTS_PATH,
                query=_query(("status", status), ("cursor", cursor), ("limit", limit)),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            MerchantUsageEventsPage,
        )

    async def iter(
        self,
        *,
        status: MerchantUsageEventStatus | _Omitted = OMITTED,
        cursor: str | _Omitted = OMITTED,
        limit: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> AsyncIterator[MerchantUsageEvent]:
        """Iterate usage events across all pages.

        Pages are fetched lazily. limit controls each page, not the total.

        Args:
            status: Status filter.
            cursor: Continuation cursor from a previous page.
            limit: Maximum number of items per page, 1 to 200.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Yields:
            MerchantUsageEvent records in server order.
        """
        next_cursor = cursor
        while True:
            page = await self.list(
                status=status,
                cursor=next_cursor,
                limit=limit,
                extra_headers=extra_headers,
                timeout=timeout,
            )
            for item in page.events:
                yield item
            if page.next_cursor is None:
                return
            next_cursor = page.next_cursor

    async def get(
        self,
        event_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> MerchantUsageEventResponse:
        """Fetch one usage event.

        Args:
            event_id: Merchant usage event identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            The event and its next_action.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "GET",
                f"{_EVENTS_PATH}/{path_segment('event_id', event_id)}",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            MerchantUsageEventResponse,
        )

    async def summary(
        self,
        *,
        days: int | _Omitted = OMITTED,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> MerchantUsageSummaryResponse:
        """Fetch delivery health: status counts and a daily window.

        Args:
            days: UTC days in the daily window, 1 to 90. Defaults to 14.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            All-time status counts and per-day delivery totals.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "GET",
                f"{_EVENTS_PATH}/summary",
                query=_query(("days", days)),
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            MerchantUsageSummaryResponse,
        )

    async def retry(
        self,
        event_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> MerchantUsageEventResponse:
        """Send a failed or uncertain event again.

        Args:
            event_id: Merchant usage event identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            The event after the request.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "POST",
                f"{_EVENTS_PATH}/{path_segment('event_id', event_id)}/retry",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            MerchantUsageEventResponse,
        )

    async def release(
        self,
        event_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> MerchantUsageEventResponse:
        """Send an unmapped event after you bind its end user.

        Args:
            event_id: Merchant usage event identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            The event after the request.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "POST",
                f"{_EVENTS_PATH}/{path_segment('event_id', event_id)}/release",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            MerchantUsageEventResponse,
        )

    async def discard(
        self,
        event_id: str,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: Timeout | _Omitted = OMITTED,
    ) -> MerchantUsageEventResponse:
        """Stop delivering an event.

        Args:
            event_id: Merchant usage event identifier.
            extra_headers: Headers for this request. Authorization uses the client
                API key.
            timeout: Request timeout override. OMITTED inherits the client timeout.

        Returns:
            The event after the request.

        Raises:
            APIStatusError: The API returns a non-success status.
            APIConnectionError: The HTTP request fails before a complete response.
            APITimeoutError: The HTTP request times out.
        """
        return await self._transport.request(
            _Request(
                "POST",
                f"{_EVENTS_PATH}/{path_segment('event_id', event_id)}/discard",
                extra_headers=extra_headers,
                timeout=timeout,
            ),
            MerchantUsageEventResponse,
        )
