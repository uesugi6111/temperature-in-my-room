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
SUMMARY_PATH = DATA_DIR / "summary.json"
SUMMARY_RETENTION_DAYS = 90


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


def append_record(record: dict, now: datetime) -> None:
    """月次NDJSONファイルに1レコードを追記する。"""
    month_path = DATA_DIR / f"{now.strftime('%Y-%m')}.ndjson"
    with month_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _running_avg(old_avg, value, count: int):
    """既存平均とサンプル数から新しい平均を返す。value が None なら既存値を保持。"""
    if value is None:
        return old_avg
    if old_avg is None or count == 0:
        return round(float(value), 1)
    return round((old_avg * count + value) / (count + 1), 1)


def update_summary(record: dict, now: datetime) -> None:
    """summary.json の当該時間バケットを増分更新し、保持期間外を間引く。"""
    bucket_ts = now.replace(minute=0, second=0, microsecond=0).isoformat(timespec="seconds")
    if SUMMARY_PATH.exists():
        summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    else:
        summary = {"unit": "hour", "points": []}

    points = summary.get("points", [])
    bucket = next((p for p in points if p["timestamp"] == bucket_ts), None)
    if bucket is None:
        bucket = {"timestamp": bucket_ts, "temperature": None, "humidity": None, "count": 0}
        points.append(bucket)

    count = bucket["count"]
    bucket["temperature"] = _running_avg(bucket["temperature"], record["temperature"], count)
    bucket["humidity"] = _running_avg(bucket["humidity"], record["humidity"], count)
    bucket["count"] = count + 1

    cutoff = (now.replace(minute=0, second=0, microsecond=0)
              - timedelta(days=SUMMARY_RETENTION_DAYS)).isoformat(timespec="seconds")
    points = [p for p in points if p["timestamp"] >= cutoff]
    points.sort(key=lambda p: p["timestamp"])

    summary["unit"] = "hour"
    summary["updated"] = now.isoformat(timespec="seconds")
    summary["points"] = points
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
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

    append_record(record, now)
    update_summary(record, now)

    print(f"記録しました: {record}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
