#!/bin/sh
set -eu

mkdir -p /data
chown -R agora:agora /data

exec gosu agora "$@"
