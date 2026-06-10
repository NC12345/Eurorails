#!/usr/bin/env python3
"""Local web server for entering route cards into route_cards.json."""

import json
import re
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).parent
ROUTE_CARDS_FILE = ROOT / "route_cards.json"
CITIES_FILE = ROOT / "cities_to_resources.json"
RESOURCES_FILE = ROOT / "resources_to_cities.json"

VALID_CITIES = sorted(json.loads(CITIES_FILE.read_text()).keys())
VALID_RESOURCES = sorted(json.loads(RESOURCES_FILE.read_text()).keys())
VALID_CITY_SET = set(VALID_CITIES)
VALID_RESOURCE_SET = set(VALID_RESOURCES)

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Route Card Entry</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 700px; margin: 40px auto; padding: 0 20px; background: #f5f5f5; }
  h1 { font-size: 1.4rem; margin-bottom: 4px; }
  #counter { color: #666; margin-bottom: 24px; }
  .row { display: flex; gap: 10px; align-items: center; margin-bottom: 12px; }
  .row label { width: 64px; text-align: right; color: #555; font-size: 0.9rem; }
  .row input[list] { flex: 2; padding: 7px 10px; border: 1px solid #ccc; border-radius: 6px; font-size: 1rem; }
  .row input[type=number] { width: 80px; padding: 7px 10px; border: 1px solid #ccc; border-radius: 6px; font-size: 1rem; }
  .row span { color: #999; font-size: 0.85rem; }
  button { padding: 9px 22px; font-size: 1rem; border: none; border-radius: 6px; cursor: pointer; }
  #preview-btn { background: #2563eb; color: #fff; }
  #preview-btn:hover { background: #1d4ed8; }
  #preview { display: none; background: #fff; border: 1px solid #d1d5db; border-radius: 8px; padding: 18px 22px; margin-top: 20px; }
  #preview h2 { font-size: 1.1rem; margin: 0 0 12px; }
  .preview-row { margin: 6px 0; font-size: 1rem; }
  .preview-row strong { color: #111; }
  .preview-actions { display: flex; gap: 10px; margin-top: 16px; }
  #confirm-btn { background: #16a34a; color: #fff; }
  #confirm-btn:hover { background: #15803d; }
  #edit-btn { background: #e5e7eb; color: #111; }
  #msg { margin-top: 16px; font-size: 0.95rem; min-height: 1.4em; }
  .err { color: #dc2626; }
  .ok { color: #16a34a; }
  .col-labels { display: flex; gap: 10px; margin-bottom: 4px; padding-left: 74px; }
  .col-labels span { flex: 2; font-size: 0.78rem; color: #888; font-weight: 600; text-transform: uppercase; letter-spacing: .04em; }
  .col-labels .ecu-label { width: 80px; flex: none; font-size: 0.78rem; color: #888; font-weight: 600; text-transform: uppercase; letter-spacing: .04em; }
</style>
</head>
<body>
<h1>Route Card Entry</h1>
<p id="counter">Loading...</p>

<datalist id="cities-list"></datalist>
<datalist id="resources-list"></datalist>

<div class="col-labels">
  <span>City</span>
  <span>Resource</span>
  <span class="ecu-label">ECU</span>
</div>

<div class="row">
  <label>Route 1</label>
  <input list="cities-list" id="city1" placeholder="City..." autocomplete="off">
  <input list="resources-list" id="res1" placeholder="Resource..." autocomplete="off">
  <input type="number" id="amt1" placeholder="0" min="1">
</div>
<div class="row">
  <label>Route 2</label>
  <input list="cities-list" id="city2" placeholder="City..." autocomplete="off">
  <input list="resources-list" id="res2" placeholder="Resource..." autocomplete="off">
  <input type="number" id="amt2" placeholder="0" min="1">
</div>
<div class="row">
  <label>Route 3</label>
  <input list="cities-list" id="city3" placeholder="City..." autocomplete="off">
  <input list="resources-list" id="res3" placeholder="Resource..." autocomplete="off">
  <input type="number" id="amt3" placeholder="0" min="1">
</div>

<button id="preview-btn" onclick="showPreview()">Preview Card</button>

<div id="preview">
  <h2>Confirm this card?</h2>
  <div id="preview-rows"></div>
  <div class="preview-actions">
    <button id="confirm-btn" onclick="saveCard()">Confirm &amp; Save</button>
    <button id="edit-btn" onclick="hidePreview()">Edit</button>
  </div>
</div>

<p id="msg"></p>

<script>
let data = {};

async function init() {
  const res = await fetch('/data');
  data = await res.json();
  const cl = document.getElementById('cities-list');
  const rl = document.getElementById('resources-list');
  data.cities.forEach(c => { const o = document.createElement('option'); o.value = c; cl.appendChild(o); });
  data.resources.forEach(r => { const o = document.createElement('option'); o.value = r; rl.appendChild(o); });
  document.getElementById('counter').textContent = data.count + ' card' + (data.count !== 1 ? 's' : '') + ' saved';
}

function getRoutes() {
  const routes = [];
  for (let i = 1; i <= 3; i++) {
    routes.push({
      city_name: document.getElementById('city' + i).value.trim(),
      resource_name: document.getElementById('res' + i).value.trim(),
      amount: parseInt(document.getElementById('amt' + i).value, 10),
    });
  }
  return routes;
}

function showPreview() {
  const routes = getRoutes();
  for (let i = 0; i < 3; i++) {
    const r = routes[i];
    if (!r.city_name || !r.resource_name || !r.amount || r.amount <= 0) {
      setMsg('Route ' + (i + 1) + ': all fields required.', true);
      return;
    }
  }
  setMsg('');
  const div = document.getElementById('preview-rows');
  div.innerHTML = routes.map(r =>
    `<div class="preview-row">${r.city_name} &larr; <strong>${r.resource_name}</strong> &nbsp; ${r.amount} ECU</div>`
  ).join('');
  document.getElementById('preview').style.display = 'block';
}

function hidePreview() {
  document.getElementById('preview').style.display = 'none';
}

async function saveCard() {
  const routes = getRoutes();
  const res = await fetch('/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(routes),
  });
  const result = await res.json();
  if (result.error) {
    setMsg(result.error, true);
    hidePreview();
    return;
  }
  data.count = result.count;
  document.getElementById('counter').textContent = result.count + ' card' + (result.count !== 1 ? 's' : '') + ' saved';
  setMsg('Card #' + result.count + ' saved!', false);
  hidePreview();
  for (let i = 1; i <= 3; i++) {
    document.getElementById('city' + i).value = '';
    document.getElementById('res' + i).value = '';
    document.getElementById('amt' + i).value = '';
  }
  document.getElementById('city1').focus();
}

function setMsg(text, isErr) {
  const el = document.getElementById('msg');
  el.textContent = text;
  el.className = isErr ? 'err' : 'ok';
}

init();
</script>
</body>
</html>"""


def normalize_amount(value):
    digits = re.sub(r"[^0-9]", "", str(value))
    if not digits:
        raise ValueError(f"Cannot parse amount: {value!r}")
    return int(digits)


def card_key(card):
    return tuple(sorted((r["city_name"], r["resource_name"], r["amount"]) for r in card))


def load_existing():
    if ROUTE_CARDS_FILE.exists():
        return json.loads(ROUTE_CARDS_FILE.read_text())
    return []


class CardHandler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # suppress request logs

    def _send_json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            body = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/data":
            existing = load_existing()
            self._send_json(200, {
                "cities": VALID_CITIES,
                "resources": VALID_RESOURCES,
                "count": len(existing),
            })
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        if urlparse(self.path).path != "/save":
            self._send_json(404, {"error": "not found"})
            return

        length = int(self.headers.get("Content-Length", 0))
        try:
            routes = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, ValueError):
            self._send_json(400, {"error": "Invalid JSON body."})
            return

        if not isinstance(routes, list) or len(routes) != 3:
            self._send_json(400, {"error": "Expected exactly 3 routes."})
            return

        card = []
        for i, r in enumerate(routes, 1):
            city = r.get("city_name", "")
            resource = r.get("resource_name", "")
            amount_raw = r.get("amount")

            if city not in VALID_CITY_SET:
                self._send_json(400, {"error": f"Route {i}: unknown city '{city}'."})
                return
            if resource not in VALID_RESOURCE_SET:
                self._send_json(400, {"error": f"Route {i}: unknown resource '{resource}'."})
                return
            if amount_raw is None:
                self._send_json(400, {"error": f"Route {i}: amount missing."})
                return
            try:
                amount = normalize_amount(amount_raw)
                if amount <= 0:
                    raise ValueError
            except ValueError:
                self._send_json(400, {"error": f"Route {i}: amount must be a positive integer."})
                return

            card.append({"city_name": city, "resource_name": resource, "amount": amount})

        existing = load_existing()
        new_key = card_key(card)
        for ec in existing:
            if card_key(ec) == new_key:
                self._send_json(409, {"error": "Duplicate card — already in route_cards.json."})
                return

        existing.append(card)
        ROUTE_CARDS_FILE.write_text(json.dumps(existing, indent=2) + "\n")
        self._send_json(200, {"ok": True, "count": len(existing)})


def main():
    server = HTTPServer(("localhost", 8765), CardHandler)
    url = "http://localhost:8765"
    print(f"Route Card Entry running at {url}  (Ctrl+C to stop)")
    threading.Timer(0.3, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
