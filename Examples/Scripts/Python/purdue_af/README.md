# Building and running tau3mu production on the Purdue Analysis Facility

Step-by-step recipe for building this ACTS checkout and running
[`full_chain_odd_tau3mu.py`](../full_chain_odd_tau3mu.py) on a [Purdue
Analysis Facility](https://analysis-facility.physics.purdue.edu) session,
either locally or fanned out across a Dask Gateway cluster instead of
SLURM (see [`../acts_tau3mu_submit.sh`](../acts_tau3mu_submit.sh) /
[`../submitSLURM.py`](../submitSLURM.py) for the SLURM version this ports).

Run every command below from a terminal in your AF session (JupyterLab's
Terminal app, or the VS Code terminal).

## 1. Get the code

Clone under `/work`, not `/home` -- `/home` isn't visible to the
Dask/Kubernetes workers used in the production step further down.

```console
$ mkdir -p /work/users/$USER
$ cd /work/users/$USER
$ git clone --branch tau3mu_muon_system https://github.com/acts-project/acts acts_tau3mu
$ cd acts_tau3mu
$ git submodule update --init --recursive
```

Everything from here on assumes your current directory is this checkout,
i.e. `/work/users/$USER/acts_tau3mu`.

## 2. One-time environment setup

```console
$ cd /work/users/$USER/acts_tau3mu
$ Examples/Scripts/Python/purdue_af/setup_env.sh
```

This creates two pixi environments under `.purdue-af/` (`gccenv`, used
only to build; `daskenv`, used only to run a Dask production campaign).
Takes a couple of minutes. Safe to re-run.

## 3. Build

```console
$ cd /work/users/$USER/acts_tau3mu
$ Examples/Scripts/Python/purdue_af/build.sh
```

Takes 15-60 minutes depending on cache state. Uses all available cores by
default; set `BUILD_JOBS=N` to limit it, e.g. `BUILD_JOBS=16
Examples/Scripts/Python/purdue_af/build.sh`.

## 4. Run one job locally

To check the build works, run a small 10-event test:

```console
$ cd /work/users/$USER/acts_tau3mu
$ source build/python/setup.sh
$ source build/thirdparty/OpenDataDetector/this_odd.sh
$ cd Examples/Scripts/Python
$ python3.11 full_chain_odd_tau3mu.py --ttbar --events 10 --rs 42 \
      --output /tmp/odd_test --no-output-root --no-output-obj
$ ls /tmp/odd_test
```

Or, to run a single full production job the same way it will later run on
a Dask worker (same seed-hashing as `../acts_tau3mu_submit.sh`, output
tarred to `.purdue-af/output/`):

```console
$ cd /work/users/$USER/acts_tau3mu
$ Examples/Scripts/Python/purdue_af/run_one_job.sh 0 10 20
$ tar -tf .purdue-af/output/odd_output_tau3mu_run_0.tar
```

(the three arguments are job index, number of events, and pileup -- the
example above runs a quick 10-event/PU20 job; drop the last two arguments
to get the full 2000-event/PU200 defaults used in production).

## 5. Run a production campaign on a Dask Gateway cluster

Instead of submitting a SLURM array (`../submitSLURM.py`), fan jobs out
across a Dask Gateway cluster on Kubernetes. Each task runs
`run_one_job.sh` as a subprocess on a worker.

1. Create a Dask cluster (via the Purdue AF agentic-interface's
   `create_dask_cluster`, or the equivalent dashboard/notebook flow), with:
   - `pixi_project` set to `/work/users/$USER/acts_tau3mu/.purdue-af/daskenv`
   - `worker_cores` / `worker_memory` sized to taste (the original SLURM
     jobs requested 10 cores each; each job here is a single
     `full_chain_odd_tau3mu.py` process)
   - note the cluster name it gives you, e.g. `cms.xxxxxxxx`

2. Run the driver, filling in that cluster name:

   ```console
   $ cd /work/users/$USER/acts_tau3mu/.purdue-af/daskenv
   $ pixi run python ../../Examples/Scripts/Python/purdue_af/run_dask_production.py \
         --cluster-name cms.xxxxxxxx --n-jobs 500 --events-per-job 2000 --pu 200
   ```

   `--n-jobs`/`--events-per-job`/`--pu` default to the original campaign's
   500 jobs x 2000 events x PU200, so they can be omitted to match it
   exactly. Output tars land in `.purdue-af/output/` (override with the
   `TAU3MU_OUTPUT_DIR` environment variable).

At PU200 this runs at roughly 1.75 s/event (measured on a 4-core worker),
so size the worker count and `--n-jobs`/`--events-per-job` split to the
time and compute budget available before launching a full run.
