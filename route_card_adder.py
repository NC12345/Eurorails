#!/usr/bin/env python3
"""Add a route card to route_cards.json. Reads a JSON array of 3 routes from stdin."""
"""echo '[...]' | python route_card_adder.py"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
ROUTE_CARDS_FILE = ROOT / "route_cards.json"
CITIES_FILE = ROOT / "cities_to_resources.json"
RESOURCES_FILE = ROOT / "resources_to_cities.json"


def normalize_amount(value):
    if isinstance(value, int):
        return value
    digits = re.sub(r"[^0-9]", "", str(value))
    if not digits:
        raise ValueError(f"Cannot parse amount: {value!r}")
    return int(digits)


def card_key(card):
    return tuple(sorted((r["city_name"], r["resource_name"], r["amount"]) for r in card))


def main():
    raw = sys.stdin.read().strip()
    if not raw:
        print("Error: no input provided.", file=sys.stderr)
        sys.exit(1)

    try:
        routes = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON — {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(routes, list) or len(routes) != 3:
        print("Error: expected a JSON array of exactly 3 routes.", file=sys.stderr)
        sys.exit(1)

    valid_cities = set(json.loads(CITIES_FILE.read_text()).keys())
    valid_resources = set(json.loads(RESOURCES_FILE.read_text()).keys())

    card = []
    for i, r in enumerate(routes):
        city = r.get("city_name", "")
        resource = r.get("resource_name", "")
        amount_raw = r.get("amount")

        if city not in valid_cities:
            print(f"Error: route {i+1} has unknown city '{city}'.", file=sys.stderr)
            sys.exit(1)
        if resource not in valid_resources:
            print(f"Error: route {i+1} has unknown resource '{resource}'.", file=sys.stderr)
            sys.exit(1)
        if amount_raw is None:
            print(f"Error: route {i+1} missing 'amount'.", file=sys.stderr)
            sys.exit(1)

        card.append({
            "city_name": city,
            "resource_name": resource,
            "amount": normalize_amount(amount_raw),
        })

    existing = json.loads(ROUTE_CARDS_FILE.read_text()) if ROUTE_CARDS_FILE.exists() else []

    new_key = card_key(card)
    for existing_card in existing:
        if card_key(existing_card) == new_key:
            print("Warning: duplicate card — already exists in route_cards.json. Skipping.")
            sys.exit(0)

    existing.append(card)
    ROUTE_CARDS_FILE.write_text(json.dumps(existing, indent=2) + "\n")
    print(f"Added card #{len(existing)} to route_cards.json.")


if __name__ == "__main__":
    main()
