#!/usr/bin/env python3
"""Dask-parallelized tau3mu production: ports ../acts_tau3mu_submit.sh /
../submitSLURM.py from SLURM array jobs to a Purdue AF Dask Gateway cluster.

Each task runs run_one_job.sh as a subprocess on a worker (which has /work
mounted, unlike /home), exactly mirroring what the SLURM job script did:
source the LCG view + ACTS build + ODD, run full_chain_odd_tau3mu.py, drop
empty events, and tar the result to a shared output directory.

Create the cluster first (e.g. via the Purdue AF agentic-interface's
create_dask_cluster, pixi_project=<repo>/.purdue-af/daskenv), then:

    python3 run_dask_production.py --cluster-name <name> \
        --n-jobs 500 --events-per-job 2000 --pu 200

Gateway() with no arguments connects to the Kubernetes backend; pass
--gateway-address/--proxy-address for the Slurm (Hammer) backend instead.
"""
import argparse
import pathlib
import subprocess
import time

RUN_SCRIPT = str(pathlib.Path(__file__).resolve().parent / "run_one_job.sh")


def run_job(job_index, n_events, pu):
    t0 = time.time()
    proc = subprocess.run(
        ["bash", RUN_SCRIPT, str(job_index), str(n_events), str(pu)],
        capture_output=True,
        text=True,
    )
    return {
        "job_index": job_index,
        "returncode": proc.returncode,
        "wall_s": time.time() - t0,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gateway-address", default=None)
    ap.add_argument("--proxy-address", default=None)
    ap.add_argument("--cluster-name", required=True)
    ap.add_argument("--n-jobs", type=int, default=500)
    ap.add_argument("--start-index", type=int, default=0)
    ap.add_argument("--events-per-job", type=int, default=2000)
    ap.add_argument("--pu", type=int, default=200)
    args = ap.parse_args()

    from dask_gateway import Gateway

    if args.gateway_address:
        gateway = Gateway(args.gateway_address, proxy_address=args.proxy_address)
    else:
        gateway = Gateway()

    cluster = gateway.connect(args.cluster_name)
    client = cluster.get_client()
    print("Dashboard:", cluster.dashboard_link)

    job_indices = range(args.start_index, args.start_index + args.n_jobs)
    futures = [
        client.submit(run_job, i, args.events_per_job, args.pu, pure=False)
        for i in job_indices
    ]

    n_ok, n_fail = 0, 0
    for fut in futures:
        res = fut.result()
        if res["returncode"] == 0:
            n_ok += 1
            print(f"[ok]   job={res['job_index']} wall={res['wall_s']:.1f}s")
        else:
            n_fail += 1
            print(f"[FAIL] job={res['job_index']} wall={res['wall_s']:.1f}s")
            print(res["stderr_tail"])

    print(f"\nDone: {n_ok} succeeded, {n_fail} failed out of {len(futures)}")


if __name__ == "__main__":
    main()
