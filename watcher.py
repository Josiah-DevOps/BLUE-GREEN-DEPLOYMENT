import os
import time
import json
import re
from collections import deque
import requests
import subprocess

LOG_FILE = "/var/log/nginx/access.log"
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")

WINDOW_SIZE = int(os.environ.get("WINDOW_SIZE", 10))
ERROR_RATE_THRESHOLD = float(os.environ.get("ERROR_RATE_THRESHOLD", 0.5))
ALERT_COOLDOWN_SEC = int(os.environ.get("ALERT_COOLDOWN_SEC", 300))

last_pool = os.environ.get("ACTIVE_POOL", "blue")
error_window = deque(maxlen=WINDOW_SIZE)
last_alert_time = 0
in_error_state = False
error_window = deque(maxlen=WINDOW_SIZE)

# 🧩 Extract all key log parts
POOL_REGEX = re.compile(r'pool=(\w+)')
RELEASE_REGEX = re.compile(r'release=([\w\.-]+)')
STATUS_REGEX = re.compile(r'upstream_status=([\d, ]+)')
UPSTREAM_REGEX = re.compile(r'upstream=([\d\.:, ]+)')
REQ_TIME_REGEX = re.compile(r'request_time=(\d+\.\d+)')
UP_RESP_TIME_REGEX = re.compile(r'upstream_response_time=([\d\., ]+)')

def post_slack(message):
    """Send formatted message to Slack."""
    global last_alert_time
    now = time.time()
    if now - last_alert_time < ALERT_COOLDOWN_SEC:
        return
    payload = {"text": message}
    try:
        requests.post(SLACK_WEBHOOK_URL, data=json.dumps(payload),
                      headers={'Content-Type': 'application/json'})
        last_alert_time = now
    except Exception as e:
        print("Slack alert failed:", e)

def tail(fpath):
    """Continuously read new lines from the file."""
    process = subprocess.Popen(
        ["tail", "-F", fpath],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    for line in process.stdout:
        yield line

for line in tail(LOG_FILE):
    pool_match = POOL_REGEX.search(line)
    release_match = RELEASE_REGEX.search(line)
    status_match = STATUS_REGEX.search(line)
    upstream_match = UPSTREAM_REGEX.search(line)
    req_time_match = REQ_TIME_REGEX.search(line)
    up_resp_time_match = UP_RESP_TIME_REGEX.search(line)

    if not pool_match or not status_match:
        continue

    pool = pool_match.group(1)
    release = release_match.group(1) if release_match else "-"
    status = status_match.group(1)
    upstream = upstream_match.group(1) if upstream_match else "-"
    req_time = req_time_match.group(1) if req_time_match else "-"
    up_resp_time = up_resp_time_match.group(1) if up_resp_time_match else "-"

    # --- FAILOVER DETECTION ---
    if pool != last_pool:
        message = (
            f"🚨 *Failover Detected*\n"
            f"Pool switched: {last_pool} → {pool}\n"
            f"Details:\n"
            f"• Pool: {pool}\n"
            f"• Release: {release}\n"
            f"• Upstream Status: {status}\n"
            f"• Upstream Addr: {upstream}\n"
            f"• Request Time: {req_time}s\n"
            f"• Upstream Response Time: {up_resp_time}"
        )
        post_slack(message)
        last_pool = pool

        # ---- Error Rate Tracking ----
    error_window.append(status >= 500)
    if len(error_window) == WINDOW_SIZE:
        rate = sum(error_window) / WINDOW_SIZE * 100

        if rate > ERROR_RATE_THRESHOLD and not in_error_state:
            post_slack("⚠️ Slack Alert – High Error Rate", f"Error-rate alert triggered (> {ERROR_RATE_THRESHOLD}%)\nCurrent 5xx rate: {rate:.2f}%")
            in_error_state = True
            error_window.clear()

        elif rate <= 0.5 * ERROR_RATE_THRESHOLD and in_error_state:
            post_slack("✅ Recovery Detected", f"5xx rate back to {rate:.2f}%")
            in_error_state = False
            error_window.clear()
