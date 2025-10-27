#!/usr/bin/env sh
set -eu

TEMPLATE="${NGINX_CONF_TEMPLATE:-/etc/nginx/nginx.conf.template}"
FINAL_CONF="${NGINX_CONF:-/etc/nginx/nginx.conf}"

ACTIVE_POOL="${ACTIVE_POOL:-blue}"

BLUE_BACKUP=""
GREEN_BACKUP=""

if [ "$ACTIVE_POOL" = "blue" ]; then
  BLUE_BACKUP=""
  GREEN_BACKUP="backup"
elif [ "$ACTIVE_POOL" = "green" ]; then
  BLUE_BACKUP="backup"
  GREEN_BACKUP=""
else
  echo "Invalid ACTIVE_POOL value: '$ACTIVE_POOL'. Must be 'blue' or 'green'." >&2
  exit 1
fi

sed -e "s/__BLUE_BACKUP__/${BLUE_BACKUP}/g" \
    -e "s/__GREEN_BACKUP__/${GREEN_BACKUP}/g" \
    "$TEMPLATE" > "$FINAL_CONF"

echo " Generated nginx.conf for ACTIVE_POOL=$ACTIVE_POOL"
nginx -t -c "$FINAL_CONF"