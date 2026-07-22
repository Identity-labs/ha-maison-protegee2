# ha-maison-protegee2

Python client for **Orange Maison Protégée** (`com.orange.fr.protegee2` v5.9), reverse-engineered from the Android APK.

No official public API exists — this project talks to the same gRPC backend as the mobile app.

## API overview

| Item | Value |
|------|-------|
| Endpoint | `maison-protegee.orange.fr:443` (TLS) |
| Protocol | gRPC / protobuf |
| Service | `com.orange.erable.services.LsService` |
| Auth | `authenticate` → JWT tokens in protobuf messages |
| Alarm | `getGatewayStatus`, `gatewayCommand` |

### Alarm commands

| Action | `mode` | `status` |
|--------|--------|----------|
| Arm total | `total` | `active` |
| Arm partial | `partial` | `active` |
| Disarm | `` (empty) | `inactive` |

## Setup

```bash
cd ha-maison-protegee2
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## Usage

### Python

```python
from maison_protegee import MaisonProtegeeClient

with MaisonProtegeeClient("your_customer_id", "your_password") as client:
    client.login()
    print(client.get_gateway_status())
    client.arm_total()
    client.disarm()
    print(client.list_equipment())
```

### CLI

```bash
export MAISON_PROTEGEE_USERNAME="..."
export MAISON_PROTEGEE_PASSWORD="..."

maison-protegee login
maison-protegee status
maison-protegee arm-total
maison-protegee disarm
maison-protegee equipment
maison-protegee events
```

## Project layout

```
ha-maison-protegee2/
├── maison_protegee/          # Python package
│   ├── client.py             # Main gRPC client
│   ├── models.py             # AlarmMode, GatewayState, …
│   ├── cli.py                # Command-line interface
│   ├── proto/erable.proto    # Reverse-engineered protobuf
│   └── generated/            # protoc output (erable_pb2*.py)
├── custom_components/
│   └── maison_protegee/      # Home Assistant integration (gRPC)
│       └── lib/maison_protegee/  # Vendored client (sync via scripts/sync_ha_lib.sh)
├── scripts/
│   ├── generate_proto.sh     # Regenerate stubs after proto edits
│   ├── extract_apk_urls.py   # Static APK string extraction
│   ├── parse_mitm_flows.py   # Parse mitmproxy captures
│   └── frida/                # Certificate unpinning helpers
└── reverse/                  # RE notes & APK metadata
```

## Regenerate protobuf stubs

After editing `maison_protegee/proto/erable.proto`:

```bash
./scripts/generate_proto.sh
```

## Reverse engineering source

Protobuf field numbers were extracted from decompiled Java classes in:

- `com.orange.erable.services.*` (gRPC service)
- `ne/a.java` → host `maison-protegee.orange.fr`
- `com.orange.fr.protegee2.data.base.a` → gRPC metadata headers

The full decompiled APK (~200 MB) can stay in the sibling `ha/` workspace folder and is gitignored here.

## Implemented RPC methods

- `authenticate`
- `getDefaultContract`
- `getGatewayStatus`
- `gatewayCommand`
- `equipmentQueryList`
- `eventQueryList`

67 RPC methods exist in the app; extend `erable.proto` + `client.py` as needed.

## Home Assistant integration

A custom component is included, mirroring [ha-maison-protegee](https://github.com/identity-labs/ha-maison-protegee) but using the gRPC client instead of web scraping.

The gRPC client is **vendored** under `custom_components/maison_protegee/lib/` so a normal HACS / folder install works without `pip install` into Home Assistant’s venv. After editing the root `maison_protegee/` package, run `./scripts/sync_ha_lib.sh`.

### Install

**HACS (recommended)** — add this repo as a custom repository (Integration), install **Maison Protegee (gRPC)**, restart Home Assistant.

**Manual**

```bash
# Copy only the integration folder into HA config
cp -R custom_components/maison_protegee /config/custom_components/
```

Or clone + symlink (also works; bootstrap finds the repo-root package):

```bash
cd /config
git clone https://github.com/identity-labs/ha-maison-protegee2.git
ln -sfn /config/ha-maison-protegee2/custom_components/maison_protegee custom_components/maison_protegee
```

Restart Home Assistant, then add **Maison Protegee** via Settings → Devices & services.

> If you see `Invalid handler specified` / *Le flux de configuration n'a pas pu être chargé*, the integration folder is incomplete (missing `lib/maison_protegee`) or an old `maison_protegee` custom component is conflicting. Remove any previous install, copy/sync the full `custom_components/maison_protegee` tree (including `lib/`), restart, and check Settings → System → Logs for `Error occurred loading flow for integration maison_protegee`.

### Entities (v2)

| Platform | Entity | Description |
|----------|--------|-------------|
| `alarm_control_panel` | Alarm | Total = arm away, partial = arm home, disarm |
| `sensor` | Room temperatures | Per-zone °C from equipment API |
| `sensor` | Latest event | Most recent log entry |
| `sensor` | Contract / Gateway ID | Diagnostics |

**Device registry:** one Orange hub device groups all entities.

**Automations:** listen for `maison_protegee_event` (includes `event_id`, `event_type`, `message`, …).

**Services:** use standard `alarm_control_panel` services — `alarm_arm_away`, `alarm_arm_home`, `alarm_disarm`.

### Options

Toggle alarm panel, temperatures, events, and diagnostic sensors independently.

> **Note:** Do not install alongside the legacy [ha-maison-protegee](https://github.com/identity-labs/ha-maison-protegee) integration — both use domain `maison_protegee`.

## Limitations

- Unofficial API — may break on app updates
- Token refresh re-logs in when JWT is near expiry
- Cameras use a separate WebRTC/signaling stack (`protectline.fr`)
- Use at your own risk; respect Orange ToS
