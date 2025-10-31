import os
import time
import json
import re
from collections import deque
import requests
import subprocess

LOG_FILE = "/var/log/nginx/access.log"
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
WINDOW_SIZE = int(os.environ.get("WINDOW_SIZE", 200))
ERROR_RATE_THRESHOLD = float(os.environ.get("ERROR_RATE_THRESHOLD", 2))
ALERT_COOLDOWN_SEC = int(os.environ.get("ALERT_COOLDOWN_SEC", 300))
last_pool = os.environ.get("ACTIVE_POOL")
error_window = deque(maxlen=WINDOW_SIZE)
last_alert_time = 0

POOL_REGEX = re.compile(r'pool=(\w+)')
STATUS_REGEX = re.compile(r'upstream_status=(\d+)')

def post_slack(message):
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
    status_match = STATUS_REGEX.search(line)
    if not pool_match or not status_match:
        continue

    pool = pool_match.group(1)
    status = int(status_match.group(1))

    # Detect failover
    if pool != last_pool:
        post_slack(f"Failover detected: {last_pool} → {pool}")
        last_pool = pool

    # Track error rate
    error_window.append(status >= 500)
    if len(error_window) == WINDOW_SIZE:
        rate = sum(error_window)/WINDOW_SIZE * 100
        if rate > ERROR_RATE_THRESHOLD:
            post_slack(f"High 5xx error rate: {rate:.2f}% over last {WINDOW_SIZE} requests")
            error_window.clear()
