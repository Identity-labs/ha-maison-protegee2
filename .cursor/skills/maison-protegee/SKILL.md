---
name: maison-protegee-ha
description: >-
  Work on the ha-maison-protegee2 Home Assistant custom component for Orange
  Maison Protégée. Use when editing entities, config flow, coordinator, HACS
  metadata, or the vendored lib/ sync. The gRPC client lives in
  ha-maison-protegee2-api.
---

# Maison Protégée Home Assistant integration

Custom component in `custom_components/maison_protegee/`. The gRPC client is **not** in this repo — it lives in sibling `ha-maison-protegee2-api` (`src/maison_protegee`).

Until that package is on PyPI, HACS uses the vendored copy at `custom_components/maison_protegee/lib/`. After API changes:

```bash
./scripts/sync_ha_lib.sh
```

A missing `lib/` tree causes HA `Invalid handler specified` when opening the config flow.

When `ha-maison-protegee2-api` is published, add it to `manifest.json` `requirements` and keep or drop the vendor copy.

See the API repo skill (`ha-maison-protegee2-api/.cursor/skills/maison-protegee/`) for login, metadata, protobuf, and RPC details.
