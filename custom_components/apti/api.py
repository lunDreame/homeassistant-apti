"""Async API client for APTi."""

from __future__ import annotations

from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientSession
from yarl import URL

from .const import API_BASE_URL

DEFAULT_TIMEOUT_SECONDS = 20


class APTiApiError(Exception):
    """Raised when the APTi API returns an error."""


class APTiAuthError(APTiApiError):
    """Raised when APTi authentication fails."""


class APTiClient:
    """Thin async client for the APTi mobile APIs."""

    def __init__(self, session: ClientSession, account_id: str, password: str) -> None:
        self._session = session
        self._account_id = account_id
        self._password = password
        self._mbl_token: str | None = None

    @property
    def account_id(self) -> str:
        """Return configured account id."""
        return self._account_id

    @property
    def mbl_token(self) -> str | None:
        """Return current mobile token."""
        return self._mbl_token

    async def async_login(self, *, force: bool = False) -> dict[str, Any]:
        """Authenticate using phone login and cache mbl-token."""
        if self._mbl_token and not force:
            return {"mblToken": self._mbl_token}

        payload = await self._request(
            "POST",
            "/api/v2/login/phone",
            auth_required=False,
            retry_on_auth=False,
            json_body={
                "id": self._account_id,
                "password": self._password,
                "plainText": self._password,
            },
        )

        token = payload.get("mblToken") or payload.get("mbl_token")
        if not token:
            raise APTiAuthError(
                payload.get("message")
                or payload.get("description")
                or "APTi login failed (missing token)"
            )

        self._mbl_token = token
        return payload

    async def async_check_token(self) -> dict[str, Any]:
        """Validate current session token."""
        return await self._request("POST", "/api/v2/user/check-token")

    async def async_get_user_information_v2(self) -> dict[str, Any]:
        """Fetch user profile (v2)."""
        return await self._request("POST", "/api/v2/user/information")

    async def async_get_user_information_v3(self) -> dict[str, Any] | None:
        """Fetch user profile (v3). Returns None when endpoint is unavailable."""
        try:
            return await self._request("GET", "/v3/api/users/information")
        except APTiApiError:
            return None

    async def async_get_user_information_detail_v3(self) -> dict[str, Any] | None:
        """Fetch user detail profile (v3). Returns None when endpoint is unavailable."""
        try:
            return await self._request("GET", "/v3/api/users/information/detail")
        except APTiApiError:
            return None

    async def async_get_manage_home(self, bill_ym: str | None = None) -> dict[str, Any]:
        """Fetch management home summary."""
        path = "/api/v2/manage/home"
        if bill_ym:
            path = f"{path}/{bill_ym}"
        return await self._request("GET", path)

    async def async_get_management_fee_history(
        self, bill_ym: str | None = None
    ) -> dict[str, Any]:
        """Fetch management fee detail."""
        path = "/v3/api/management-fee/history"
        if bill_ym:
            path = f"{path}/{bill_ym}"
        return await self._request("GET", path)

    async def async_get_management_payment_history(
        self, state_code: str
    ) -> list[dict[str, Any]]:
        """Fetch payment history by state code."""
        data = await self._request("GET", f"/v3/api/management-fee/payment/{state_code}")
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]
        return []

    async def async_get_manage_payment_next(self) -> dict[str, Any] | None:
        """Fetch next payment info."""
        try:
            return await self._request("GET", "/api/v2/manage/payment-next")
        except APTiApiError:
            return None

    async def async_get_manage_auto_discount(self) -> dict[str, Any] | None:
        """Fetch auto discount info."""
        try:
            return await self._request("GET", "/api/v2/manage/auto-discount")
        except APTiApiError:
            return None

    async def async_get_manage_energy(self) -> dict[str, Any] | None:
        """Fetch energy summary."""
        try:
            return await self._request("GET", "/api/v2/manage/energy")
        except APTiApiError:
            return None

    async def async_get_parking_visit(self, based_month: str) -> dict[str, Any] | None:
        """Fetch parking visit and reservation info."""
        try:
            return await self._request(
                "GET",
                "/api/parking/v2/visit",
                params={"basedMonth": based_month},
            )
        except APTiApiError:
            return None

    async def async_get_parking_favorites(self) -> list[dict[str, Any]] | None:
        """Fetch parking favorites."""
        try:
            data = await self._request("POST", "/api/parking/v2/favorites", json_body={})
        except APTiApiError:
            return None
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]
        return None

    async def async_get_parking_application_status(self) -> dict[str, Any] | None:
        """Fetch parking application status."""
        try:
            return await self._request("POST", "/api/parking/v2/application/status")
        except APTiApiError:
            return None

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        auth_required: bool = True,
        retry_on_auth: bool = True,
    ) -> dict[str, Any] | list[Any]:
        """Execute an API request with optional one-time auth retry."""
        if auth_required and not self._mbl_token:
            await self.async_login()

        url = str(URL(API_BASE_URL).with_path(path))
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "HomeAssistant-APTi/0.1",
        }
        if auth_required and self._mbl_token:
            headers["mbl-token"] = self._mbl_token

        try:
            async with self._session.request(
                method=method,
                url=url,
                params=params,
                json=json_body,
                headers=headers,
                timeout=DEFAULT_TIMEOUT_SECONDS,
            ) as response:
                payload = await self._decode_json(response)

                if auth_required and retry_on_auth and self._is_auth_failure(response.status, payload):
                    await self.async_login(force=True)
                    return await self._request(
                        method,
                        path,
                        params=params,
                        json_body=json_body,
                        auth_required=auth_required,
                        retry_on_auth=False,
                    )

                if response.status >= 400:
                    message = self._extract_error_message(payload)
                    if response.status in (401, 403):
                        raise APTiAuthError(message)
                    raise APTiApiError(message)

                return payload
        except APTiAuthError:
            raise
        except (ClientError, ClientResponseError, TimeoutError) as err:
            raise APTiApiError(str(err)) from err

    async def _decode_json(self, response) -> dict[str, Any] | list[Any]:
        """Decode JSON payload; if body is empty return an empty dict."""
        text = await response.text()
        if not text:
            return {}
        try:
            parsed = await response.json(content_type=None)
        except ValueError as err:
            raise APTiApiError(f"Non-JSON response: {text[:160]}") from err
        if isinstance(parsed, (dict, list)):
            return parsed
        raise APTiApiError("Unexpected API response type")

    def _is_auth_failure(self, http_status: int, payload: dict[str, Any] | list[Any]) -> bool:
        """Detect auth-expired conditions."""
        if http_status in (401, 403):
            return True
        if isinstance(payload, dict):
            status = str(payload.get("status", ""))
            code = str(payload.get("code", ""))
            message = str(payload.get("message", ""))
            if status in {"90001", "90002", "90005"}:
                return True
            if code in {"90001", "90002", "90005"}:
                return True
            if "로그인" in message and ("만료" in message or "필요" in message):
                return True
        return False

    def _extract_error_message(self, payload: dict[str, Any] | list[Any]) -> str:
        """Extract best-effort error message from payload."""
        if isinstance(payload, dict):
            for key in ("message", "description", "status", "code"):
                value = payload.get(key)
                if value not in (None, ""):
                    return str(value)
        return "APTi API request failed"

