import json

cards = []
with open("route_cards.txt") as f:
    for line in f:
        parts = line.split()
        if len(parts) != 10:
            continue
        _, c1, r1, a1, c2, r2, a2, c3, r3, a3 = parts
        cards.append([
            {"city_name": c1, "resource_name": r1, "amount": int(a1)},
            {"city_name": c2, "resource_name": r2, "amount": int(a2)},
            {"city_name": c3, "resource_name": r3, "amount": int(a3)},
        ])

print(f"Parsed {len(cards)} cards")

with open("route_cards.json", "w") as f:
    json.dump(cards, f, indent=2)

print("Written to route_cards.json")
