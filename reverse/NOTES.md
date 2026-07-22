# Reverse engineering notes — Maison Protégée v5.9

## APK

- Package: `com.orange.fr.protegee2`
- Version: 5.9 (`version_code` 20260529)
- XAPK splits: base + `config.armeabi_v7a` + `config.en` + `config.mdpi`

## gRPC channel

From `ne/a.java`:

```java
OkHttpChannelBuilder.forAddress("maison-protegee.orange.fr", 443)
    .useTransportSecurity()
```

## Request metadata

From `com.orange.fr/protegee2/data/base/a.java`:

| Header | Value |
|--------|-------|
| `version` | App version, e.g. `5.9` |
| `trustBadge` | Didomi statistics consent (`true`/`false`) |
| `hasheduserid` | SHA-256 hex of `username.upper()` |
| `app_request_id` | Optional UUID |

## Login flow

1. `authenticate(AuthenticationRequest { customerId, password })`
2. Response → `AuthentificationToken { accessToken, refreshToken }`
3. `getDefaultContract(ContractInfoListRequest { token, username })`
4. Response → `contractId`, `gateway.gatewayId`, `gateway.gatewayType`

## Token usage

- Most calls embed `AuthentificationToken` in the protobuf body (not Bearer header)
- Equipment/events endpoints use raw `accessToken` string in `authorizationHeader` / `token` fields
- After login, many calls duplicate `accessToken` as both access and refresh token fields

## gRPC methods (67 total)

See `LsServiceGrpc.java` — key methods for HA:

- `authenticate`, `getDefaultContract`
- `getGatewayStatus`, `gatewayCommand`
- `equipmentQueryList`, `eventQueryList`
- `getHomeModeSettings`, `setHomeModeSettings`

## Secondary endpoints

| Purpose | Host |
|---------|------|
| Camera WebRTC signaling | `signalingserver-ws.teamusages.prod.protectline.fr` |
| Web views (IBAN, etc.) | `digit-mobile-fe.teamoffre.prod.protectline.fr` |
| Firebase | `app-maison-protegee.firebaseio.com` |

## Status codes

Backend uses `ORS-200`, `ORS-401`, `ORS-408`, etc. (see `ORSExceptionCode.java`).
