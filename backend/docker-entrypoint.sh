#!/bin/sh
set -e

# Railway mounts volumes as root. Hand the data directory to the app user, then drop privileges.
if [ "$(id -u)" = "0" ]; then
  if [ -n "$DATA_DIR" ]; then
    mkdir -p "$DATA_DIR"
    chown -R app:app "$DATA_DIR"
  fi
  exec setpriv --reuid=app --regid=app --init-groups -- "$@"
fi

exec "$@"
