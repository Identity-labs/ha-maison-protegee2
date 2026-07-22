"""gRPC client for Orange Maison Protégée.

Reverse-engineered from com.orange.fr.protegee2 v5.9.
API endpoint: maison-protegee.orange.fr:443 (TLS)
Service: com.orange.erable.services.LsService
"""

from __future__ import annotations

import base64
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

import grpc

from maison_protegee.exceptions import ApiError, AuthenticationError
from maison_protegee.generated import erable_pb2, erable_pb2_grpc
from maison_protegee.models import AlarmMode, AlarmStatus, GatewayState, SessionInfo

DEFAULT_HOST = "maison-protegee.orange.fr:443"
APP_VERSION = "5.9"
# Envoy RBAC on maison-protegee.orange.fr rejects grpc-python's default user-agent.
# The Android app ships io.grpc 1.76.0 over OkHttp (see GrpcUtil.IMPLEMENTATION_VERSION).
GRPC_USER_AGENT = "grpc-java-okhttp/1.76.0"
SUCCESS_STATUS = "ORS-200"


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _ors_code(status: str) -> str:
    """Map backend codes like ORS0100200 to ORS-200 (same as cb.h.m in the app)."""
    value = status.strip()
    if len(value) > 7:
        return f"ORS-{value[-3:]}"
    return value


def _normalize_status(status: str) -> str:
    return _ors_code(status).replace("-", "").upper()


def _is_success(status: str) -> bool:
    return _normalize_status(status) == "ORS200"


def _is_contract_success(status: str) -> bool:
    code = _normalize_status(status)
    return code in {"ORS200", "ORS206", "ORS428"}


def _jwt_expiry(access_token: str) -> Optional[datetime]:
    try:
        parts = access_token.split(".")
        if len(parts) < 2:
            return None
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload))
        exp = data.get("exp")
        if exp is None:
            return None
        return datetime.fromtimestamp(int(exp), tz=timezone.utc)
    except Exception:
        return None


class MaisonProtegeeClient:
    """Client for the Orange Maison Protégée gRPC API."""

    def __init__(
        self,
        username: str,
        password: str,
        *,
        host: str = DEFAULT_HOST,
        app_version: str = APP_VERSION,
        trust_badge: bool = False,
        timeout: float = 30.0,
    ) -> None:
        self._username = username.strip()
        self._password = password
        self._host = host
        self._app_version = app_version
        self._trust_badge = trust_badge
        self._timeout = timeout

        self._channel: Optional[grpc.Channel] = None
        self._stub: Optional[erable_pb2_grpc.LsServiceStub] = None

        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._hashed_user_id: str = _sha256_hex(self._username.upper())
        self._contract_id: Optional[str] = None
        self._gateway_id: Optional[str] = None
        self._gateway_type: Optional[str] = None

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> MaisonProtegeeClient:
        self.connect()
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def connect(self) -> None:
        if self._channel is None:
            self._channel = grpc.secure_channel(
                self._host,
                grpc.ssl_channel_credentials(),
                options=(("grpc.primary_user_agent", GRPC_USER_AGENT),),
            )
            self._stub = erable_pb2_grpc.LsServiceStub(self._channel)

    def close(self) -> None:
        if self._channel is not None:
            self._channel.close()
        self._channel = None
        self._stub = None

    @property
    def session(self) -> SessionInfo:
        self._require_logged_in()
        return SessionInfo(
            access_token=self._access_token or "",
            refresh_token=self._refresh_token or "",
            username=self._username.upper(),
            hashed_user_id=self._hashed_user_id,
            contract_id=self._contract_id or "",
            gateway_id=self._gateway_id or "",
            gateway_type=self._gateway_type or "",
        )

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def login(self) -> SessionInfo:
        """Authenticate and load contract/gateway identifiers."""
        self.connect()
        assert self._stub is not None

        try:
            auth_resp = self._stub.authenticate(
                erable_pb2.AuthenticationRequest(
                    customerId=self._username,
                    password=self._password,
                ),
                metadata=self._metadata(for_login=True),
                timeout=self._timeout,
            )
        except grpc.RpcError as exc:
            if exc.code() == grpc.StatusCode.PERMISSION_DENIED:
                raise ApiError(
                    "RBAC",
                    "access denied by API gateway — ensure grpc-java-okhttp user-agent is set",
                ) from exc
            raise
        self._check_response(auth_resp.status, auth_resp.message)

        if not auth_resp.HasField("result"):
            raise AuthenticationError("authenticate returned no token")

        token = auth_resp.result
        self._access_token = token.accessToken
        self._refresh_token = token.refreshToken

        customer_id = (token.customerId or self._username).strip()
        if not customer_id:
            raise AuthenticationError("authenticate returned no customerId")

        self._username = customer_id.upper()
        self._hashed_user_id = _sha256_hex(self._username)

        contract_resp = self._stub.getDefaultContract(
            erable_pb2.ContractInfoListRequest(
                authentificationToken=self._token_message(
                    self._access_token,
                    self._refresh_token,
                ),
                username=self._username,
            ),
            metadata=self._metadata(),
            timeout=self._timeout,
        )
        self._check_contract_response(contract_resp.status, contract_resp.message)

        if not contract_resp.result:
            raise ApiError(contract_resp.status, "no contract returned for this account")

        contract = self._select_contract(contract_resp.result)
        self._contract_id = contract.contractId
        self._gateway_id = None
        self._gateway_type = None
        if contract.HasField("gateway"):
            gateway_id = contract.gateway.gatewayId.strip()
            if gateway_id:
                self._gateway_id = gateway_id
                self._gateway_type = contract.gateway.gatewayType or None

        return self.session

    def ensure_token_valid(self) -> None:
        """Re-login if the JWT access token is expired or about to expire."""
        if not self._access_token:
            self.login()
            return
        expiry = _jwt_expiry(self._access_token)
        if expiry is None:
            return
        remaining = (expiry - datetime.now(timezone.utc)).total_seconds()
        if remaining < 300:
            self.login()

    # ------------------------------------------------------------------
    # Gateway / alarm
    # ------------------------------------------------------------------

    def get_gateway_status(self) -> GatewayState:
        self.ensure_token_valid()
        self._require_gateway()
        assert self._stub is not None

        resp = self._stub.getGatewayStatus(
            erable_pb2.SystemStateQueryRequest(
                authentificationToken=self._token_message(self._access_token, ""),
                gatewayId=self._gateway_id,
            ),
            metadata=self._metadata(),
            timeout=self._timeout,
        )
        self._check_response(resp.status, resp.message)

        if not resp.HasField("result"):
            raise ApiError(resp.status, "getGatewayStatus returned no result")

        r = resp.result
        return GatewayState.from_result(r.mode, r.status, r.delay)

    def gateway_command(self, mode: AlarmMode, status: AlarmStatus) -> GatewayState:
        self.ensure_token_valid()
        self._require_gateway()
        assert self._stub is not None

        resp = self._stub.gatewayCommand(
            erable_pb2.GatewayCommandRequest(
                authentificationToken=self._token_message(
                    self._access_token,
                    self._access_token,
                ),
                idGateway=self._gateway_id,
                mode=mode.value,
                status=status.value,
            ),
            metadata=self._metadata(),
            timeout=self._timeout,
        )
        self._check_response(resp.status, resp.message)

        if resp.HasField("result"):
            r = resp.result
            return GatewayState.from_result(r.mode, r.status, r.delay)
        return self.get_gateway_status()

    def arm_total(self) -> GatewayState:
        return self.gateway_command(AlarmMode.TOTAL, AlarmStatus.ACTIVE)

    def arm_partial(self) -> GatewayState:
        return self.gateway_command(AlarmMode.PARTIAL, AlarmStatus.ACTIVE)

    def disarm(self) -> GatewayState:
        return self.gateway_command(AlarmMode.NONE, AlarmStatus.INACTIVE)

    # ------------------------------------------------------------------
    # Equipment & events
    # ------------------------------------------------------------------

    def list_equipment(self, equipment_type: int = 0) -> erable_pb2.EquipmentListQueryResponse:
        self.ensure_token_valid()
        assert self._stub is not None

        resp = self._stub.equipmentQueryList(
            erable_pb2.EquipmentListQueryRequest(
                authorizationHeader=self._access_token,
                contractId=self._contract_id,
                equipementType=equipment_type,
            ),
            metadata=self._metadata(),
            timeout=self._timeout,
        )
        self._check_response(resp.status, resp.message)
        return resp

    def list_events(self, limit: int = 20) -> erable_pb2.EventListQueryResponse:
        self.ensure_token_valid()
        assert self._stub is not None

        resp = self._stub.eventQueryList(
            erable_pb2.EventListQueryRequest(
                contractId=self._contract_id,
                limit=str(limit),
                token=self._access_token,
            ),
            metadata=self._metadata(),
            timeout=self._timeout,
        )
        self._check_response(resp.status, resp.message)
        return resp

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _metadata(
        self,
        *,
        for_login: bool = False,
        app_request_id: Optional[str] = None,
    ) -> Iterable[tuple[str, str]]:
        md = [
            ("version", self._app_version),
            ("trustbadge", "true" if self._trust_badge else "false"),
            ("hasheduserid", "" if for_login else self._hashed_user_id),
        ]
        rid = app_request_id or str(uuid.uuid4()).lower()
        if rid:
            md.append(("app_request_id", rid))
        return md

    @staticmethod
    def _token_message(
        access_token: Optional[str],
        refresh_token: Optional[str],
    ) -> erable_pb2.AuthentificationToken:
        return erable_pb2.AuthentificationToken(
            accessToken=access_token or "",
            refreshToken=refresh_token or "",
        )

    @staticmethod
    def _check_contract_response(status: str, message: str) -> None:
        if _is_contract_success(status):
            return
        if _normalize_status(status) == "ORS404":
            raise ApiError(status, message or "no Maison Protégée contract found for this account")
        if _normalize_status(status) == "ORS401":
            raise AuthenticationError(message or status)
        raise ApiError(status, message)

    @staticmethod
    def _check_response(status: str, message: str) -> None:
        if not _is_success(status):
            if _normalize_status(status) == "ORS401":
                raise AuthenticationError(message or status)
            raise ApiError(status, message)

    @staticmethod
    def _select_contract(
        contracts: Iterable[erable_pb2.ContractDetailsResult],
    ) -> erable_pb2.ContractDetailsResult:
        items = list(contracts)
        if not items:
            raise ApiError("ORS404", "no contract returned for this account")
        for contract in items:
            if contract.HasField("gateway") and contract.gateway.gatewayId.strip():
                return contract
        return items[0]

    def _require_logged_in(self) -> None:
        if not self._access_token or not self._contract_id:
            raise AuthenticationError("not logged in — call login() first")

    def _require_gateway(self) -> None:
        self._require_logged_in()
        if not self._gateway_id:
            raise ApiError(
                "ORS428",
                "contract has no gateway — alarm commands are unavailable until installation is complete",
            )
