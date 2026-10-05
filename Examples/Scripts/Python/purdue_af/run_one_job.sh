#!/bin/bash
# Runs one tau3mu production job: the Dask-task equivalent of
# ../acts_tau3mu_submit.sh's SLURM body. Called by run_dask_production.py on
# a worker, but also runnable by hand for a quick local test.
#
# Usage: run_one_job.sh <job_index> [n_events] [pileup]

NJOB=$1
NEVENTS=${2:-2000}
NPU=${3:-200}

# Same seed derivation as acts_tau3mu_submit.sh: hash the job index (Murmur3
# fmix32) instead of passing it directly, since RandomNumbers::generateSeed
# does seed = base_seed + eventNumber, so sequential small job indices fed
# straight into std::mt19937 produce correlated streams across jobs.
h=$(( NJOB ^ 0x9E3779B9 ))
h=$(( (h ^ (h >> 16)) & 0xFFFFFFFF ))
h=$(( (h * 0x85ebca6b) & 0xFFFFFFFF ))
h=$(( (h ^ (h >> 13)) & 0xFFFFFFFF ))
h=$(( (h * 0xc2b2ae35) & 0xFFFFFFFF ))
SEED=$(( (h ^ (h >> 16)) & 0xFFFFFFFF ))

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../../.." && pwd)"
STATE="$ROOT/.purdue-af"
BUILD="$ROOT/build"
OUTBASE="${TAU3MU_OUTPUT_DIR:-$STATE/output}"

# NOTE: not using `set -e` here. The LCG view's setup.sh runs a battery of
# optional auto-detections for tools we don't use (R, Julia, gnuplot, ...),
# and on the Dask/k8s worker image at least one of those (R, missing
# libreadline.so.7) exits non-zero -- sourcing that under `set -e` would
# abort this whole script before it ever got to running the production. We
# check the actual production step's exit code explicitly below instead.
source /cvmfs/sft.cern.ch/lcg/views/LCG_107/x86_64-el8-gcc11-opt/setup.sh
GCCENV="$STATE/gccenv/.pixi/envs/default"
export LD_LIBRARY_PATH="$GCCENV/lib:$LD_LIBRARY_PATH"
# The Dask/k8s worker pod image is a leaner base than the interactive AF
# session: it lacks libcurl (needed by ROOT's shared libs), and lacks
# glibc-devel entirely (no /usr/include/assert.h etc, needed by ROOT's
# cling JIT when it shells back out to gcc). Supply both from the same
# self-contained gccenv used at build time rather than relying on the host.
export CPATH="$GCCENV/x86_64-conda-linux-gnu/sysroot/usr/include:$CPATH"
source "$BUILD/python/setup.sh"
source "$BUILD/thirdparty/OpenDataDetector/this_odd.sh"

cd "$ROOT/Examples/Scripts/Python"

LOCALOUT=$(mktemp -d "/tmp/odd_output_tau3mu_run_${NJOB}.XXXXXX")
trap 'rm -rf "$LOCALOUT"' EXIT

echo "job=${NJOB} seed=${SEED} events=${NEVENTS} pu=${NPU} host=$(hostname) localout=${LOCALOUT}"

python3.11 full_chain_odd_tau3mu.py --ttbar --ttbar-pu "${NPU}" --events "${NEVENTS}" --rs "${SEED}" \
    --output "$LOCALOUT" --no-output-root --no-output-obj
RC=$?
if [ "$RC" -ne 0 ]; then
    echo "full_chain_odd_tau3mu.py failed with exit code $RC" >&2
    exit "$RC"
fi

# Drop events with no simulated particles (tau3mu filter rejected them),
# same intent as cleanEmptyEvents.py but driven off the files that actually
# exist rather than a hardcoded event-count loop.
python3.11 - "$LOCALOUT" <<'PYEOF'
import csv
import glob
import os
import sys

folder = sys.argv[1]
suffixes = [
    "cells.csv", "hits.csv", "hits.obj", "hits_trajectory.obj",
    "measurements.csv", "measurement-simhit-map.csv", "particles.csv",
    "particles_simulated.csv", "seed.csv", "track_parameters_ambi.csv",
    "track_parameters_ckf.csv", "tracks_ambi.csv", "tracks_ckf.csv",
]
for f in sorted(glob.glob(os.path.join(folder, "event*-particles_simulated.csv"))):
    with open(f, newline="") as fh:
        rows = sum(1 for _ in csv.reader(fh))
    if rows == 1:  # header only, no particles survived
        prefix = f[: -len("particles_simulated.csv")]
        for suffix in suffixes:
            p = prefix + suffix
            if os.path.exists(p):
                os.remove(p)
PYEOF

mkdir -p "$OUTBASE"
tar -cf "$OUTBASE/odd_output_tau3mu_run_${NJOB}.tar" -C "$(dirname "$LOCALOUT")" "$(basename "$LOCALOUT")"

echo "DONE job=${NJOB} seed=${SEED}"
