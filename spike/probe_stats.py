# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "python-dotenv"]
# ///
"""Discovery spike for the boost.ai Statistics API v2.

Purpose (phase 0 in the plan): authenticate via OAuth2 client_credentials and
probe all relevant statistics endpoints against the tenant for a short date
range. For each call the raw JSON response is saved under spike/out/, and a
summary markdown report (_report.md) is written with status and top-level field
names.

Nothing is written to a database here. The output feeds the PDD and schema design.

Run:  uv run --script spike/probe_stats.py
Requires a filled-in .env (see .env.example).
"""

import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

OUT_DIR = Path(__file__).parent / "out"
REQUEST_TIMEOUT = 60

# Stats served by distribution/histogram/heatmap (path enum from the docs).
DISTRIBUTION_STATS = [
    "authentication", "click", "conversation_feedback", "conversation_quality",
    "conversation_review", "duration", "statusboard_conversation_quality",
    "device", "no_utterance_conversations", "human_chat", "message_feedback",
    "message", "sentiment", "nlu_stats", "nlu_statusboard",
]

# Stats served by frequency (path enum from the docs).
FREQUENCY_STATS = [
    "analytics_tag", "click_from_meta_action", "click_to_meta_action",
    "displayed_meta_action", "external_api_status", "filter", "goals_completed",
    "goals_started", "guardrail", "human_chat_agent", "human_chat_skill",
    "language", "link", "predicted_intent", "predicted_label",
    "sent_filter_value", "source_url", "system_action_trigger", "van_node",
    "action_link", "url_link", "asu_type", "prediction_type", "van_type",
]


def get_token(tenant: str, client_id: str, client_secret: str, scope: str) -> str:
    """Obtain an OAuth2 access token via the client_credentials flow."""
    url = f"https://{tenant}.boost.ai/api/oauth2/v1/token"
    resp = requests.post(
        url,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": scope,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=REQUEST_TIMEOUT,
    )
    if not resp.ok:
        raise SystemExit(
            f"Token request failed ({resp.status_code}) against {url}\n"
            f"Response: {resp.text}\n"
            "Check BOOST_CLIENT_ID/SECRET and that BOOST_SCOPE matches the "
            "client's scope in the Admin Panel (e.g. 'analytics:v1').")
    return resp.json()["access_token"]


def probe(session: requests.Session, base_url: str, path: str, body: dict,
          params: dict | None = None) -> dict:
    """Call a single endpoint and return a structured result (without raising)."""
    url = f"{base_url}{path}"
    try:
        resp = session.post(url, json=body, params=params, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        return {"path": path, "params": params, "ok": False, "error": repr(exc)}

    result = {"path": path, "params": params, "status": resp.status_code,
              "ok": resp.ok}
    try:
        result["response"] = resp.json()
    except ValueError:
        result["response"] = resp.text
    return result


def top_level_keys(response: object) -> str:
    """Readable description of the response shape for the report."""
    if isinstance(response, dict):
        keys = list(response.keys())
        # Distribution responses look like {label, distribution: {...}} -> show fields.
        if isinstance(response.get("distribution"), dict):
            return f"distribution fields: {list(response['distribution'].keys())}"
        if "headers" in response:
            return f"headers: {response.get('headers')}"
        return f"keys: {keys}"
    if isinstance(response, list):
        return f"list ({len(response)} elements)"
    return type(response).__name__


def require_env(*names: str) -> None:
    """Exit with a friendly message if required .env variables are missing."""
    missing = [name for name in names if not os.environ.get(name)]
    if missing:
        raise SystemExit(
            "Missing .env variables: " + ", ".join(missing) + ".\n"
            "Copy .env.example to .env and fill it in (see the plan).")


def main() -> None:
    """Run the whole spike: token -> probe all stats -> dump JSON + report."""
    load_dotenv()
    require_env("BOOST_TENANT", "BOOST_CLIENT_ID", "BOOST_CLIENT_SECRET",
                "SPIKE_FROM_DATE", "SPIKE_TO_DATE")
    tenant = os.environ["BOOST_TENANT"]
    client_id = os.environ["BOOST_CLIENT_ID"]
    client_secret = os.environ["BOOST_CLIENT_SECRET"]
    scope = os.environ.get("BOOST_SCOPE", "analytics:v1")
    from_date = os.environ["SPIKE_FROM_DATE"]
    to_date = os.environ["SPIKE_TO_DATE"]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    base_url = f"https://{tenant}.boost.ai/api/external/statistics/v2"
    search_filter = {"from_date": from_date, "to_date": to_date}

    print(f"Fetching token for tenant '{tenant}' (scope: {scope})...")
    token = get_token(tenant, client_id, client_secret, scope)
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })

    # Build the list of calls: (label, path, body, params).
    probes: list[tuple[str, str, dict, dict | None]] = []
    for stat in DISTRIBUTION_STATS:
        probes.append((f"distribution__{stat}", f"/distribution/{stat}",
                       search_filter, None))
    for stat in FREQUENCY_STATS:
        probes.append((f"frequency__{stat}", f"/frequency/{stat}",
                       search_filter, {"limit": 25}))
    probes.append(("frequency__nlu", "/frequency/nlu", search_filter, None))
    probes.append(("aggregates__token_usage", "/aggregates/token_usage",
                   search_filter, None))
    # Representative histogram (conversations over time) + the "unknown answers" filter.
    probes.append(("histogram__message_day", "/histogram/message",
                   {**search_filter, "group_by": "day"}, None))
    probes.append(("frequency__predicted_label_unknown",
                   "/frequency/predicted_label",
                   {**search_filter, "unknown_responses_only": True},
                   {"limit": 25}))

    report_lines = [
        "# boost.ai Statistics API v2 — discovery spike",
        "",
        f"Tenant: `{tenant}`  |  Range: `{from_date}` -> `{to_date}` (excl.)",
        "",
        "| Probe | Status | Shape / fields |",
        "|-------|--------|----------------|",
    ]

    for label, path, body, params in probes:
        result = probe(session, base_url, path, body, params)
        (OUT_DIR / f"{label}.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

        if result.get("ok"):
            shape = top_level_keys(result.get("response"))
            status = "200 OK"
        elif "status" in result:
            status = str(result["status"])
            shape = str(result.get("response"))[:120]
        else:
            status = "ERROR"
            shape = result.get("error", "")[:120]

        report_lines.append(f"| `{label}` | {status} | {shape} |")
        print(f"  {label}: {status}")

    report_text = "\n".join(report_lines) + "\n"
    (OUT_DIR / "_report.md").write_text(report_text, encoding="utf-8")
    print(f"\nDone. See {OUT_DIR / '_report.md'} and the individual *.json files.")


if __name__ == "__main__":
    main()
