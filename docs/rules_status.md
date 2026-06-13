# Eurorails — Rules Implementation Status

Legend: ✅ Done | ⚠️ Partial / Needs Fix | ❌ Not Implemented

---

## 1. Map & Topology

| Rule | Status | Notes |
|------|--------|-------|
| Terrain types (clear/mountain/alpine/small_city/medium_city/large_city/ferry/ferry_small_city/space_sea) | ✅ | hex_node.py |
| Water obstacles on edges (river, lake) | ✅ | neighbors dict in master_map.json; surcharges in hex_node.py |
| space_sea skipped in render/pathfinding | ✅ | |

---

## 2. Setup & Starting Conditions

| Rule | Status | Notes |
|------|--------|-------|
| Start with 50M ECU | ✅ | game_state.py:526 |
| Start with Freight loco | ✅ | game_state.py:527 |
| Start with 3 demand cards | ✅ | prototype.py:513-516 |
| Exactly 3 demand cards enforced (hand limit) | ⚠️ | Implicit via deliver-replace; no explicit validator |
| Event card drawn → resolve + redraw until 3 cards | ❌ | No event card system |
| 2 pre-game build-only turns (20M each, no upgrades) | ✅ | INITIAL_BUILD_1/2 phases; track_builder.py:41-46 |
| Turn order via deck-cut (highest payout = first) | ❌ | Not implemented |
| Snake draft for pre-game turns (CW then CCW) | ❌ | Phases exist, rotation logic missing |

---

## 3. Turn Structure

| Rule | Status | Notes |
|------|--------|-------|
| Operate phase before build phase | ✅ | execute_operate → execute_build order |
| Max 20M spend per build phase | ✅ | track_builder.py:65-66 |
| Build OR upgrade — never both | ✅ | track_builder.py:38-46 |
| Track built this turn usable next turn only | ✅ | staged_edges committed separately from owned_edges |

### Operation Phase

| Rule | Status | Notes |
|------|--------|-------|
| Start train at any city | ⚠️ | current_node field exists; no validation that position is a city node |
| Movement allowance = loco max speed | ✅ | game_state.py:91, movement.py:56 |
| Reversing blocked on open track | ✅ | movement.py:150-155 |
| Reverse allowed inside city / major city / ferry port | ✅ | same check |
| Major city interior: free travel (1MP/node, no track needed) | ✅ | movement.py:134; hex_node.py:84-91 |
| No track building inside major city red zone | ✅ | track_builder.py:121-122 |
| Pickup free, no movement penalty | ✅ | movement.py:185-214 |
| Can carry goods without matching demand card | ✅ | no card check at pickup |
| Drop anywhere, free, returns to supply | ✅ | movement.py:217-227 |
| Deliver: payout + discard card + draw replacement + continue movement | ✅ | movement.py:230-282 |
| Opponent track usage fee: 4M per opponent per turn | ✅ | movement.py:131-147 |
| Cash check before entering opponent track | ✅ | movement.py:143-146 |
| Fees settled at end of operate phase | ✅ | movement.py:289-302 |
| Ferry: enter port → stop all movement, committed_to_ferry=True | ✅ | movement.py:166-182 |
| Ferry: next turn teleport to opposite port at half speed | ✅ | movement.py:89-97 |
| Half-speed rounded up (Freight 9→5, Fast 12→6) | ✅ | Bug: code uses `//` floor division → Freight gets 4 not 5. Should use `math.ceil`. movement.py:94 (FIXED)|
| Discard hand (draw 3 new cards, end turn immediately) | ❌ | No action type, no executor, no tests |

---

## 4. Track Building

| Rule | Status | Notes |
|------|--------|-------|
| Build cost: clear=1, mountain=2, alpine=5, small/medium city=3, large city=5 | ✅ | hex_node.py:16-23 |
| River surcharge +2M | ✅ | hex_node.py:26-29 |
| Lake surcharge +3M | ✅ | hex_node.py:26-29 |
| Ocean inlet surcharge +3M | ✅ | mapped to lake surcharge |
| Multiple water crossings to one milepost: surcharge applied once | ✅ | |
| Ferry crossing cost: paid at first port; second port free | ✅ | track_builder.py:192-195 |
| No credit — can't spend what you don't have | ✅ | track_builder.py:83-84 |
| Right of way (one track per edge total) | ✅ | track_builder.py:114-128 |
| Start construction from any major city or owned track | ✅ | track_builder.py:173 |
| Major city touch limit: max 2 sections per player per build phase | ✅ | track_builder.py:131-147 |
| Guaranteed right to connect to every major city | ⚠️ | Tier-1 local saturation check only; full BFS TODO at track_builder.py:279 |
| Medium city: max 3 players | ✅ | track_builder.py:233 |
| Small city: max 2 players | ✅ | track_builder.py:233 |
| No player > 3 sections into one medium/small city | ✅ | track_builder.py:255-258 |
| Blocking rule (can't block guaranteed access minimums) | ⚠️ | Tier-1 only; no BFS over wider graph |
| Only 2 players per ferry line | ❌ | Not checked |
| Guaranteed right to at least one English Channel ferry | ❌ | Not implemented |

---

## 5. Locomotive Upgrades

| Rule | Status | Notes |
|------|--------|-------|
| Freight starting train (speed 9, cap 2) | ✅ | |
| Fast Freight (12, 2) costs 20M from Freight | ✅ | game_state.py:55-60 |
| Heavy Freight (9, 3) costs 20M from Freight | ✅ | game_state.py:55-60 |
| Superfreight (12, 3) costs 20M from Fast or Heavy | ✅ | game_state.py:55-60 |
| Invalid upgrade path rejected | ✅ | track_builder.py:203-215 |
| Upgrades blocked during initial build phases | ✅ | track_builder.py:41-43 |

---

## 6. Event Cards

| Rule | Status | Notes |
|------|--------|-------|
| Event cards in deck (20 cards) | ❌ | disaster_cards.json is empty stub |
| Draw event → resolve immediately, display publicly | ❌ | |
| Active until end of drawing player's next turn | ❌ | |
| Strikes (block pickup/delivery by coastal region) | ❌ | |
| Taxes (graduated scale, all players disclose cash) | ❌ | |
| Derailments (trains within 3 mileposts: lose 1 turn + discard 1 cargo) | ❌ | |
| Bad weather (half-rate movement, restrict mountain/alpine/marine building) | ❌ | |
| Floods (erase track on named river; block rebuild until card expires) | ❌ | |

---

## 7. Victory Conditions

| Rule | Status | Notes |
|------|--------|-------|
| Win: continuous track connecting 7 major cities | ❌ | No check_victory() exists |
| Win: 250M ECU liquid cash simultaneously | ❌ | |
| Tournament: finish current round after victory declared | ❌ | |
| Tie-break: highest cash | ❌ | |

---

## Summary

| Category | ✅ Done | ⚠️ Partial | ❌ Missing |
|----------|---------|-----------|-----------|
| Map & Topology | 3 | 0 | 0 |
| Setup | 4 | 1 | 3 |
| Turn Structure | 4 | 0 | 0 |
| Operation Phase | 11 | 2 | 1 |
| Track Building | 10 | 2 | 2 |
| Loco Upgrades | 6 | 0 | 0 |
| Event Cards | 0 | 0 | 8 |
| Victory | 0 | 0 | 4 |
| **Total** | **38** | **5** | **18** |

## Bugs to Fix

1. **Blocking rule BFS** — [track_builder.py:279](../track_builder.py#L279): Tier-2 full-graph connectivity check is TODO; only local saturation is checked.
