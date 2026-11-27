#!/bin/bash
# Runs one tau3mu (signal) or minimum-bias (background) production job: the
# Dask-task equivalent of ../acts_tau3mu_submit.sh's SLURM body. Called by
# run_dask_production.py on a worker, but also runnable by hand for a quick
# local test.
#
# Usage: run_one_job.sh <job_index> [n_events] [pileup] [tau3mu|minbias]

NJOB=$1
NEVENTS=${2:-2000}
NPU=${3:-200}
SAMPLE=${4:-tau3mu}

case "$SAMPLE" in
    tau3mu) SIM_SCRIPT=full_chain_odd_tau3mu.py ;;
    minbias) SIM_SCRIPT=full_chain_odd_minbias.py ;;
    *)
        echo "unknown sample: $SAMPLE (expected tau3mu or minbias)" >&2
        exit 2
        ;;
esac

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

# Thread count: the ACTS Sequencer's default (-1) asks TBB for one thread per
# visible CPU, and inside a Kubernetes pod that is the whole node (128-256 on
# the AF's Dask nodes) -- the pod's CPU limit is a CFS quota, not a cpuset, so
# neither nproc nor TBB sees it. Each of those threads keeps a full PU200 event
# in flight, so memory scales with the node's core count rather than the
# worker's, and the job is OOM-killed (exit 137) by its own worker's memory
# limit; meanwhile hundreds of threads fight over a 4-core quota. Read the
# quota from the cgroup instead (v2, then v1), capped at nproc -- run without
# OMP_NUM_THREADS, which nproc obeys and Dask sets to 1 on every worker.
# TAU3MU_THREADS overrides it.
if [ -z "$TAU3MU_THREADS" ]; then
    QUOTA="" PERIOD=""
    if [ -r /sys/fs/cgroup/cpu.max ]; then
        read -r QUOTA PERIOD < /sys/fs/cgroup/cpu.max
    elif [ -r /sys/fs/cgroup/cpu/cpu.cfs_quota_us ]; then
        QUOTA=$(cat /sys/fs/cgroup/cpu/cpu.cfs_quota_us)
        PERIOD=$(cat /sys/fs/cgroup/cpu/cpu.cfs_period_us)
    fi
    if [[ "$QUOTA" =~ ^[0-9]+$ ]] && [ "$QUOTA" -gt 0 ] && [ "${PERIOD:-0}" -gt 0 ]; then
        TAU3MU_THREADS=$(( (QUOTA + PERIOD - 1) / PERIOD ))
    fi
    if [ -z "$TAU3MU_THREADS" ] || [ "$TAU3MU_THREADS" -gt "$(env -u OMP_NUM_THREADS nproc)" ]; then
        TAU3MU_THREADS=$(env -u OMP_NUM_THREADS nproc)
    fi
fi

# FPE monitoring off: the Sequencer fails the whole job if any floating-point
# exception is not covered by one of ACTS's FPE masks, but masks are matched
# by source file and line, which this Release build (no debug info, no
# libbacktrace in this toolchain) cannot resolve -- so no mask ever matches.
# Fatras's known-benign underflow in pow() (masked upstream in
# SimulationActor.hpp, #2346) then shows up in roughly one PU200 event in a
# few hundred and throws away every event of the job. Monitoring only
# observes; the simulated events are identical with it off.
export ACTS_SEQUENCER_DISABLE_FPEMON=1

cd "$ROOT/Examples/Scripts/Python"

LOCALOUT=$(mktemp -d "/tmp/odd_output_${SAMPLE}_run_${NJOB}.XXXXXX")
trap 'rm -rf "$LOCALOUT"' EXIT

echo "sample=${SAMPLE} job=${NJOB} seed=${SEED} events=${NEVENTS} pu=${NPU} threads=${TAU3MU_THREADS} host=$(hostname) localout=${LOCALOUT}"

python3.11 "$SIM_SCRIPT" --ttbar --ttbar-pu "${NPU}" --events "${NEVENTS}" --rs "${SEED}" --threads "${TAU3MU_THREADS}" \
    --output "$LOCALOUT" --no-output-root --no-output-obj
RC=$?
if [ "$RC" -ne 0 ]; then
    echo "$SIM_SCRIPT failed with exit code $RC" >&2
    exit "$RC"
fi

# $SIM_SCRIPT has already dropped events the tau3mu filter rejected (if
# any) and slimmed the rest to muon-system hits (--muon-system-only, on
# by default; see muon_system_slim.py).
mkdir -p "$OUTBASE"
tar -czf "$OUTBASE/odd_output_${SAMPLE}_run_${NJOB}.tar.gz" -C "$(dirname "$LOCALOUT")" "$(basename "$LOCALOUT")"

echo "DONE job=${NJOB} seed=${SEED}"
