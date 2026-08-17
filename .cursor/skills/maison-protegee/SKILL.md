---
name: maison-protegee-ha
description: >-
  Work on the ha-maison-protegee2 Home Assistant custom component for Orange
  Maison Protégée. Use when editing entities, config flow, coordinator, HACS
  metadata, or the PyPI client dependency. The gRPC client lives in
  ha-maison-protegee2-api.
---

# Maison Protégée Home Assistant integration

Custom component in `custom_components/maison_protegee/`. The gRPC client is **not** in this repo — it lives in sibling `ha-maison-protegee2-api` (`src/maison_protegee`) and is installed from PyPI as `ha-maison-protegee2-api`.

Declare the dependency in `custom_components/maison_protegee/manifest.json`:

```json
"requirements": ["ha-maison-protegee2-api>=0.1.0"]
```

Import `maison_protegee` directly (Home Assistant installs requirements before loading the integration). Do not vendor the client under `lib/` and do not add a `sys.path` bootstrap.

See the API repo skill (`ha-maison-protegee2-api/.cursor/skills/maison-protegee/`) for login, metadata, protobuf, and RPC details.
