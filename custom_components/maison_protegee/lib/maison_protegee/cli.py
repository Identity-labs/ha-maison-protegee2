#!/usr/bin/env python3
"""CLI for Orange Maison Protégée."""

from __future__ import annotations

import argparse
import json
import os
import sys

from maison_protegee.client import MaisonProtegeeClient
from maison_protegee.exceptions import MaisonProtegeeError


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Missing environment variable: {name}")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Orange Maison Protégée CLI")
    parser.add_argument(
        "--username",
        default=os.environ.get("MAISON_PROTEGEE_USERNAME", ""),
        help="Customer ID (or MAISON_PROTEGEE_USERNAME)",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("MAISON_PROTEGEE_PASSWORD", ""),
        help="Password (or MAISON_PROTEGEE_PASSWORD)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("login", help="Authenticate and print session info")
    sub.add_parser("status", help="Get gateway/alarm status")
    sub.add_parser("arm-total", help="Arm alarm (total)")
    sub.add_parser("arm-partial", help="Arm alarm (partial)")
    sub.add_parser("disarm", help="Disarm alarm")
    sub.add_parser("equipment", help="List equipment")
    sub.add_parser("events", help="List recent events")

    args = parser.parse_args(argv)
    username = args.username or _env("MAISON_PROTEGEE_USERNAME")
    password = args.password or _env("MAISON_PROTEGEE_PASSWORD")

    try:
        with MaisonProtegeeClient(username, password) as client:
            if args.command == "login":
                session = client.login()
                print(json.dumps(session.__dict__, indent=2))
            elif args.command == "status":
                client.login()
                state = client.get_gateway_status()
                print(json.dumps(state.__dict__, indent=2, default=str))
            elif args.command == "arm-total":
                client.login()
                state = client.arm_total()
                print(json.dumps(state.__dict__, indent=2, default=str))
            elif args.command == "arm-partial":
                client.login()
                state = client.arm_partial()
                print(json.dumps(state.__dict__, indent=2, default=str))
            elif args.command == "disarm":
                client.login()
                state = client.disarm()
                print(json.dumps(state.__dict__, indent=2, default=str))
            elif args.command == "equipment":
                client.login()
                resp = client.list_equipment()
                items = []
                for group in resp.equipmentListResult:
                    for eq in group.equipmenList:
                        item = {
                            "location": group.location,
                            "model": eq.model,
                            "deviceId": eq.deviceId,
                            "name": eq.intitule,
                            "connection": eq.connection,
                            "locationDetail": eq.locationDetail,
                            "scene": eq.scene,
                        }
                        if eq.HasField("parameters"):
                            item["statusMode"] = eq.parameters.statusMode
                        if eq.HasField("attributes"):
                            item["attributes"] = {
                                "temperature": eq.attributes.temperature,
                                "status": eq.attributes.status,
                                "battery": eq.attributes.battery,
                                "signalWifi": eq.attributes.signalWifi,
                                "privacyMode": eq.attributes.privacyMode,
                            }
                        items.append(item)
                print(json.dumps(items, indent=2))
            elif args.command == "events":
                client.login()
                resp = client.list_events()
                events = [
                    {
                        "eventId": e.eventId,
                        "dateTime": e.dateTime,
                        "type": e.type,
                        "user": e.user,
                        "source": e.source,
                    }
                    for e in resp.eventList
                ]
                print(json.dumps(events, indent=2))
    except MaisonProtegeeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
