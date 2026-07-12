#!/usr/bin/env python3
"""SwitchBot 温湿度計からステータスを取得し、docs/data/ 配下のJSONへ保存する。"""
import base64
import hashlib
import hmac
import json
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API_BASE = "https://api.switch-bot.com/v1.1"
JST = timezone(timedelta(hours=9))
DATA_DIR = Path(__file__).resolve().parent.parent / "docs" / "data"


def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    return session


def build_headers(token: str, secret: str) -> dict:
    nonce = str(uuid.uuid4())
    t = str(int(time.time() * 1000))
    string_to_sign = f"{token}{t}{nonce}"
    sign = base64.b64encode(
        hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256).digest()
    ).decode("utf-8")
    return {
        "Authorization": token,
        "sign": sign,
        "t": t,
        "nonce": nonce,
        "Content-Type": "application/json; charset=utf8",
    }


def fetch_status(token: str, secret: str, device_id: str) -> dict:
    url = f"{API_BASE}/devices/{device_id}/status"
    headers = build_headers(token, secret)
    session = build_session()
    resp = session.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("statusCode") != 100:
        raise RuntimeError(f"SwitchBot API error: {payload}")
    return payload["body"]


def main() -> int:
    token = os.environ.get("SWITCHBOT_TOKEN")
    secret = os.environ.get("SWITCHBOT_SECRET")
    device_id = os.environ.get("SWITCHBOT_DEVICE_ID")
    if not all([token, secret, device_id]):
        print(
            "SWITCHBOT_TOKEN / SWITCHBOT_SECRET / SWITCHBOT_DEVICE_ID が設定されていません",
            file=sys.stderr,
        )
        return 1

    try:
        body = fetch_status(token, secret, device_id)
    except Exception as exc:  # noqa: BLE001
        print(f"データ取得に失敗しました: {exc}", file=sys.stderr)
        return 1

    now = datetime.now(JST)
    record = {
        "timestamp": now.isoformat(timespec="seconds"),
        "temperature": body.get("temperature"),
        "humidity": body.get("humidity"),
        "battery": body.get("battery"),
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    latest_path = DATA_DIR / "latest.json"
    latest_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    month_path = DATA_DIR / f"{now.strftime('%Y-%m')}.json"
    if month_path.exists():
        history = json.loads(month_path.read_text(encoding="utf-8"))
    else:
        history = []
    history.append(record)
    month_path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"記録しました: {record}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
