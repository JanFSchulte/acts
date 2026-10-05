# Building and running tau3mu production on the Purdue Analysis Facility

Recipe for building this ACTS checkout and running
[`full_chain_odd_tau3mu.py`](../full_chain_odd_tau3mu.py) on a [Purdue
Analysis Facility](https://analysis-facility.physics.purdue.edu) session,
either locally or fanned out across a Dask Gateway cluster instead of
SLURM (see [`../acts_tau3mu_submit.sh`](../acts_tau3mu_submit.sh) /
[`../submitSLURM.py`](../submitSLURM.py) for the SLURM version this ports).

## Why this isn't just `cmake -B build -S .`

The [general build instructions](../../../../docs/getting_started.md) work
by sourcing an LCG view from CVMFS and building directly against it. That
mostly works here too (LCG_107's `x86_64-el8-gcc11-opt` view on CVMFS has
Boost, ROOT, DD4hep, Geant4, Pythia8 and Qt5), but three things about this
specific container need working around:

1. **No `module` command.** The AF session is a Kubernetes pod, not a
   login node with environment-modules, so there's no `module load
   gcc/14.1.0` available the way a Slurm submit script would use. ACTS
   needs `std::format` (GCC ≥ 13); LCG_107's own GCC is 11. `setup_env.sh`
   builds a tiny pixi environment (`gccenv`) with a conda-forge GCC 13 as
   a drop-in compiler frontend, while everything else still comes from the
   LCG view. The conda-forge `g++` bakes an rpath to its own newer
   libstdc++ into everything it links, so this doesn't trip over the
   libstdc++ ABI underneath LCG's own binaries.
2. **No root, no `-devel` system packages.** DD4hep built with Geant4
   support (true of the LCG releases) makes `find_package(DD4hep)`
   transitively require Geant4's *entire* visualization stack --
   X11, OpenGL, Qt5, Motif -- even though nothing here does Geant4
   visualization. X11/OpenGL/bzip2/zlib/libcurl dev headers are missing
   system-wide and there's no `dnf install` without root, so they go into
   the same `gccenv` pixi project instead. Motif has no conda-forge package
   at all (and isn't needed for anything in this pipeline), so
   `patch_geant4_cmake.py` makes a local copy of the view's
   `Geant4Config.cmake` with just that one `find_dependency(Motif)` turned
   off, and `CMakeLists.txt` was adjusted to not propagate `REQUIRED` into
   that whole dependency chain just to build DD4hep's core geometry
   components.
3. **The Dask worker pod image is leaner than the interactive session
   image.** It's missing `libcurl` (needed by ROOT's shared libs) and
   glibc-devel entirely (no `/usr/include/assert.h`, needed when ROOT's
   cling JIT shells back out to gcc) -- `run_one_job.sh` points `CPATH`/
   `LD_LIBRARY_PATH` at the same self-contained `gccenv` sysroot rather
   than relying on the worker's own base image.

Everything below only touches this repo checkout and a `.purdue-af/`
state directory next to it (both already covered by `.gitignore`) -- no
system packages, no root.

## One-time setup

Clone (or already have this checked out) somewhere under `/work` or
`/depot`, **not** `/home` -- `/home` isn't visible to Dask/Kubernetes
workers, which matters for the parallel-production step below.

```console
$ Examples/Scripts/Python/purdue_af/setup_env.sh   # creates .purdue-af/{gccenv,daskenv}
$ Examples/Scripts/Python/purdue_af/build.sh        # configures + builds into build/
```

`build.sh` takes 15-60 minutes depending on cache state; it uses all
available cores by default (override with `BUILD_JOBS=N`).

## Running one job locally

```console
$ source build/python/setup.sh
$ source build/thirdparty/OpenDataDetector/this_odd.sh
$ cd Examples/Scripts/Python
$ python3.11 full_chain_odd_tau3mu.py --ttbar --events 10 --rs 42 \
      --output /tmp/odd_test --no-output-root --no-output-obj
```

Or, equivalently, as a single self-contained job (same seed-hashing as
`../acts_tau3mu_submit.sh`, same output layout as the SLURM version,
output tarred to `.purdue-af/output/`):

```console
$ Examples/Scripts/Python/purdue_af/run_one_job.sh <job_index> [n_events] [pileup]
```

## Running a production campaign on a Dask Gateway cluster

Instead of submitting a SLURM array (`../submitSLURM.py`), fan jobs out
across a Dask Gateway cluster on Kubernetes. Each task just runs
`run_one_job.sh` as a subprocess on a worker, so the worker environment
only needs `dask`/`distributed`/`dask-gateway` -- the production itself
still runs against the LCG view + `gccenv` + `build/`, all of which live
under `/work` and are visible to the workers.

1. Create a cluster (e.g. via the Purdue AF agentic-interface's
   `create_dask_cluster`), with:
   - `pixi_project` = `<repo>/.purdue-af/daskenv`
   - `worker_cores` / `worker_memory` sized to taste (the original SLURM
     jobs requested 10 cores each; each job here is a single
     `full_chain_odd_tau3mu.py` process)
2. Run the driver:

   ```console
   $ cd .purdue-af/daskenv
   $ pixi run python ../../Examples/Scripts/Python/purdue_af/run_dask_production.py \
         --cluster-name <name> --n-jobs 500 --events-per-job 2000 --pu 200
   ```

   `--n-jobs`/`--events-per-job`/`--pu` default to the original campaign's
   500 jobs x 2000 events x PU200. Output tars land in
   `.purdue-af/output/` (override with `TAU3MU_OUTPUT_DIR`).

At PU200 this is roughly 1.75 s/event (measured on a 4-core worker), so
size the worker count and `--n-jobs`/`--events-per-job` split to the time
and compute budget available before launching a full run.
