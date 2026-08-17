# ha-maison-protegee2

Home Assistant custom component for **Orange Maison Protégée**, using the reverse-engineered gRPC client in [ha-maison-protegee2-api](https://github.com/Identity-labs/ha-maison-protegee2-api).

Until that package is published on PyPI, this integration vendors a copy under `custom_components/maison_protegee/lib/`. After API changes, run `./scripts/sync_ha_lib.sh`. Once published, `ha-maison-protegee2-api` will be declared in `manifest.json` requirements.

Do not install alongside the legacy [ha-maison-protegee](https://github.com/identity-labs/ha-maison-protegee) integration — both use domain `maison_protegee`.

## Install

**HACS (recommended)** — add this repo as a custom repository (Integration), install **Orange Maison Protégée**, restart Home Assistant.

**Manual**

```bash
# Copy only the integration folder into HA config
cp -R custom_components/maison_protegee /config/custom_components/
```

Or clone + symlink:

```bash
cd /config
git clone https://github.com/Identity-labs/ha-maison-protegee2.git
ln -sfn /config/ha-maison-protegee2/custom_components/maison_protegee custom_components/maison_protegee
```

Restart Home Assistant, then add **Orange Maison Protégée** via Settings → Devices & services.

> If you see `Invalid handler specified` / *Le flux de configuration n'a pas pu être chargé*, the integration folder is incomplete (missing `lib/maison_protegee`) or an old `maison_protegee` custom component is conflicting. Remove any previous install, copy/sync the full `custom_components/maison_protegee` tree (including `lib/`), restart, and check Settings → System → Logs for `Error occurred loading flow for integration maison_protegee`.

## Entities

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

### Alarm commands

| Action | HA service | API mode / status |
|--------|------------|-------------------|
| Arm total | `alarm_arm_away` | `total` / `active` |
| Arm partial | `alarm_arm_home` | `partial` / `active` |
| Disarm | `alarm_disarm` | empty / `inactive` |

## Development

The gRPC client, protobuf, CLI, and reverse-engineering scripts live in [ha-maison-protegee2-api](https://github.com/Identity-labs/ha-maison-protegee2-api). Clone it next to this repo:

```bash
../ha-maison-protegee2-api/   # Python package (src/maison_protegee)
./                            # this Home Assistant integration
./scripts/sync_ha_lib.sh      # copy API package → custom_components/.../lib/
```

## Limitations

- Unofficial API — may break on app updates
- Token refresh re-logs in when JWT is near expiry
- Cameras use a separate WebRTC/signaling stack (`protectline.fr`)
- Use at your own risk; respect Orange ToS
