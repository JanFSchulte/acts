#!/bin/bash
# One-time setup: creates the two pixi environments used by build.sh and
# run_dask_production.py. Safe to re-run (pixi add is idempotent).
set -ex

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../../.." && pwd)"
STATE="$ROOT/.purdue-af"
mkdir -p "$STATE"

# gccenv: a modern (>=13) GCC used only as the compiler frontend, plus a
# handful of -devel packages this container lacks system-wide. See
# README.md for why each package is here.
if [ ! -d "$STATE/gccenv" ]; then
    pixi init "$STATE/gccenv"
fi
(cd "$STATE/gccenv" && pixi add gxx=13 xorg-libx11 xorg-xorgproto libgl-devel bzip2 zlib libcurl)

# daskenv: the client/worker environment for the Dask Gateway cluster.
# Pinned to match whatever dask/distributed the facility's own base
# environment ships, which is what the Gateway's own scheduler/workers run
# -- a mismatch here is the single most likely source of a cluster that
# comes up but can't actually run anything.
BASE_DASK_VERSION=$(/opt/pixi/.pixi/envs/base-env/bin/python -c \
    "import dask; print(dask.__version__)" 2>/dev/null || true)
if [ -z "$BASE_DASK_VERSION" ]; then
    echo "warning: could not detect the facility's own dask version; using latest" >&2
    DASK_SPEC="dask distributed"
else
    DASK_SPEC="dask==$BASE_DASK_VERSION distributed==$BASE_DASK_VERSION"
fi
if [ ! -d "$STATE/daskenv" ]; then
    pixi init "$STATE/daskenv"
fi
(cd "$STATE/daskenv" && pixi add python=3.11 dask-gateway $DASK_SPEC)

echo "Environments ready under $STATE"
