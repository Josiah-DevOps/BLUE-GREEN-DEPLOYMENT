
# Blue-Green Deployment with Docker and NGINX

This project demonstrates a **Blue-Green Deployment** setup using Docker, Docker Compose, and NGINX as a reverse proxy. The goal is to run two identical application versions (blue and green) and control which one receives live traffic, allowing seamless upgrades with minimal downtime.



## Table of Contents

1. [Overview]
2. [Components]
3. [NGINX Configuration Template]
4. [NGINX Config Generation Script]
5. [Docker Compose Setup]
6. [How It Works]
7. [Testing & Health Checks]


## Overview

In a Blue-Green Deployment:

* Two identical environments run in parallel (`blue` and `green`).
* One environment serves live traffic (`ACTIVE_POOL`).
* NGINX dynamically switches traffic between the two environments by updating its upstream configuration.
* Docker Compose orchestrates the services and networking.


## Components

* **app_blue & app_green:** Two identical application containers.
* **nginx:** Reverse proxy container that routes traffic based on the `ACTIVE_POOL`.
* **generate-nginx-conf.sh:** Script that generates the correct `nginx.conf` depending on the active pool.
* **nginx.conf.template:** NGINX configuration template with placeholders for blue/green backup.


Example:

bash
BLUE_IMAGE=yimikaade/wonderful:devops-stage-two
GREEN_IMAGE=yimikaade/wonderful:devops-stage-two
ACTIVE_POOL=blue
RELEASE_ID_BLUE=v1.0.0
RELEASE_ID_GREEN=v1.0.1
PORT=8080


## NGINX Configuration Template

`nginx.conf.template` uses **placeholders** to mark which upstream server is the primary and which is a backup:

upstream app_pool { 
    server app_blue:3000 max_fails=1 fail_timeout=3s __BLUE_BACKUP__;
    server app_green:3000 max_fails=1 fail_timeout=3s __GREEN_BACKUP__;
    keepalive 16;
}


* `__BLUE_BACKUP__` / `__GREEN_BACKUP__` are replaced with `"backup"` or `""` depending on the `ACTIVE_POOL`.
* The backup server is only used if the primary fails, enabling automatic failover.
* `proxy_pass http://app_pool;` forwards requests to the active app.


## NGINX Config Generation Script

`generate-nginx-conf.sh` dynamically generates `nginx.conf`:

#!/usr/bin/env sh
set -eu

TEMPLATE="${NGINX_CONF_TEMPLATE:-/etc/nginx/nginx.conf.template}"
FINAL_CONF="${NGINX_CONF:-/etc/nginx/nginx.conf}"
ACTIVE_POOL="${ACTIVE_POOL:-blue}"

# Determine which server is backup
if [ "$ACTIVE_POOL" = "blue" ]; then
  BLUE_BACKUP=""
  GREEN_BACKUP="backup"
elif [ "$ACTIVE_POOL" = "green" ]; then
  BLUE_BACKUP="backup"
  GREEN_BACKUP=""
else
  echo "Invalid ACTIVE_POOL value: '$ACTIVE_POOL'" >&2
  exit 1
fi

# Replace placeholders in template
sed -e "s/__BLUE_BACKUP__/${BLUE_BACKUP}/g" \
    -e "s/__GREEN_BACKUP__/${GREEN_BACKUP}/g" \
    "$TEMPLATE" > "$FINAL_CONF"

echo "Generated nginx.conf for ACTIVE_POOL=$ACTIVE_POOL"
nginx -t -c "$FINAL_CONF"


**How it works:**

1. Reads `ACTIVE_POOL`.
2. Assigns `backup` or empty string to the servers.
3. Uses `sed` to replace placeholders in the NGINX template.
4. Validates the generated NGINX configuration with `nginx -t`.



## Docker Compose Setup

`docker-compose.yml` defines three services:


services:
  app_blue:
    image: yimikaade/wonderful:devops-stage-two
    ports: ["8081:3000"]
    environment: RELEASE_ID=blue-release-001, APP_POOL=blue, PORT=3000
    healthcheck: wget http://localhost:3000/healthz

  app_green:
    image: yimikaade/wonderful:devops-stage-two
    ports: ["8082:3000"]
    environment: RELEASE_ID=green-release-001, APP_POOL=green, PORT=3000
    healthcheck: wget http://localhost:3000/healthz

  nginx:
    image: nginx:1.25-alpine
    ports: ["8080:80"]
    depends_on: [app_blue, app_green]
    volumes:
      - ./nginx.conf.template
      - ./generate-nginx-conf.sh
    environment:
      ACTIVE_POOL=${ACTIVE_POOL}
    entrypoint: ["/bin/sh", "-c", "/docker-entrypoint.d/generate-nginx-conf.sh && nginx -g 'daemon off;'"]


* **Ports 8081/8082:** Direct access to individual apps (optional).
* **Port 8080:** Access to NGINX, which routes traffic to the active pool.
* **Healthchecks:** Ensure containers are healthy before NGINX routes traffic.
* **Volumes:** Mount the template and script into the NGINX container.


## How It Works

1. Set `ACTIVE_POOL` to `blue` or `green`.
2. Docker Compose starts all three services.
3. NGINX runs the `generate-nginx-conf.sh` script on startup.
4. Script replaces placeholders in the NGINX template to mark which app is primary.
5. Requests to NGINX (`localhost:8080`) are routed to the active app (`blue` or `green`).
6. Backup server only handles requests if the primary fails (`backup` keyword).
7. Health checks ensure that failing containers are avoided.

This setup enables **zero-downtime deployments**: you can deploy a new version to the inactive environment, switch `ACTIVE_POOL`, and instantly route traffic without interrupting users.



## Testing & Health Checks

* Access active app via `http://localhost:8080/`.
* Check individual containers:

  * Blue: `http://localhost:8081/`
  * Green: `http://localhost:8082/`
* Verify NGINX config:

docker-compose exec nginx nginx -t

* Health endpoint: `http://localhost:8080/healthz` returns `nginx is healthy`.
