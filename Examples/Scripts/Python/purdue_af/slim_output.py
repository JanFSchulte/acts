#!/usr/bin/env python3
"""Slim tau3mu production output down to what muon-system studies need.

Per event this keeps
  - hits.csv rows in the muon-system volumes (MUON_VOLUMES), byte-for-byte
    as written (same columns, same precision), and
  - particles.csv / particles_simulated.csv rows for particles that left a
    hit there, plus every particle of the signal vertex (SIGNAL_PV), which
    downstream code uses to find the tau3mu muons,
and drops the tracker-only reconstruction outputs (measurements, cells,
seeds, tracks) and any OBJ/ROOT files. Anything else (timing.csv, ...) is
kept unchanged. Standard library only, so it runs under the LCG view's
python3.11 on a worker as well as anywhere else.

Two modes:

    slim_output.py dir <output_dir>
        slim a job's output directory in place (used by run_one_job.sh)

    slim_output.py tar <input.tar> <output.tar.gz>
        stream an existing production tar into a slimmed, gzipped one
"""
import argparse
import io
import os
import sys
import tarfile

# ACTS volume IDs of the ODD muon system: -z endcap, barrel, +z endcap.
MUON_VOLUMES = {4, 36, 37}
# Pythia8 vertex the tau3mu signal is generated at.
SIGNAL_PV = 1

DROP_SUFFIXES = (
    "-cells.csv",
    "-measurements.csv",
    "-measurement-simhit-map.csv",
    "-seed.csv",
    "-tracks_ckf.csv",
    "-tracks_ambi.csv",
    "-track_parameters_ckf.csv",
    "-track_parameters_ambi.csv",
    ".obj",
    ".root",
)
HITS_SUFFIX = "-hits.csv"
PARTICLE_SUFFIXES = ("-particles.csv", "-particles_simulated.csv")
# hits.csv and particles*.csv both start with these five columns.
N_KEY_COLUMNS = 5


def event_of(name):
    return os.path.basename(name).split("-")[0]


def filter_hits(text):
    """Return (kept text, particle keys with a muon-system hit, n_in, n_out)."""
    lines = text.splitlines(keepends=True)
    header = lines[0].rstrip("\r\n").split(",")
    gid_col = header.index("geometry_id")
    out = [lines[0]]
    keys = set()
    for line in lines[1:]:
        fields = line.split(",", gid_col + 1)
        if (int(fields[gid_col]) >> 56) in MUON_VOLUMES:
            out.append(line)
            keys.add(tuple(fields[:N_KEY_COLUMNS]))
    return "".join(out), keys, len(lines) - 1, len(out) - 1


def filter_particles(text, keys):
    lines = text.splitlines(keepends=True)
    out = [lines[0]]
    for line in lines[1:]:
        fields = line.split(",", N_KEY_COLUMNS)
        key = tuple(fields[:N_KEY_COLUMNS])
        if int(key[0]) == SIGNAL_PV or key in keys:
            out.append(line)
    return "".join(out)


def slim_dir(folder):
    names = sorted(os.listdir(folder))
    keys_by_event = {}
    n_in = n_out = 0
    for name in names:
        path = os.path.join(folder, name)
        if name.endswith(DROP_SUFFIXES):
            os.remove(path)
        elif name.endswith(HITS_SUFFIX):
            with open(path) as fh:
                kept, keys, a, b = filter_hits(fh.read())
            with open(path, "w") as fh:
                fh.write(kept)
            keys_by_event[event_of(name)] = keys
            n_in += a
            n_out += b
    for name in names:
        if name.endswith(PARTICLE_SUFFIXES):
            path = os.path.join(folder, name)
            with open(path) as fh:
                kept = filter_particles(fh.read(), keys_by_event.get(event_of(name), set()))
            with open(path, "w") as fh:
                fh.write(kept)
    print(f"slim: {len(keys_by_event)} events, kept {n_out}/{n_in} hits")


def add_text(tar, member, text):
    data = text.encode()
    info = tarfile.TarInfo(member.name)
    info.size = len(data)
    info.mtime = member.mtime
    info.mode = member.mode
    tar.addfile(info, io.BytesIO(data))


def slim_tar(src, dst):
    # Members come in directory order, not grouped by event, so particle
    # files are held back until every hits file has been seen.
    tmp = dst + ".part"
    keys_by_event = {}
    pending = []
    n_in = n_out = 0
    with tarfile.open(src, "r|") as tin, tarfile.open(tmp, "w:gz") as tout:
        for m in tin:
            if not m.isfile():
                tout.addfile(m)
            elif m.name.endswith(DROP_SUFFIXES):
                continue
            elif m.name.endswith(HITS_SUFFIX):
                kept, keys, a, b = filter_hits(tin.extractfile(m).read().decode())
                add_text(tout, m, kept)
                keys_by_event[event_of(m.name)] = keys
                n_in += a
                n_out += b
            elif m.name.endswith(PARTICLE_SUFFIXES):
                pending.append((m, tin.extractfile(m).read().decode()))
            else:
                tout.addfile(m, tin.extractfile(m))
        for m, text in pending:
            add_text(tout, m, filter_particles(text, keys_by_event.get(event_of(m.name), set())))
    os.replace(tmp, dst)
    print(f"slim: {src} -> {dst}: {len(keys_by_event)} events, kept {n_out}/{n_in} hits")
    return {"events": len(keys_by_event), "hits_in": n_in, "hits_out": n_out}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)
    d = sub.add_parser("dir")
    d.add_argument("folder")
    t = sub.add_parser("tar")
    t.add_argument("src")
    t.add_argument("dst")
    args = ap.parse_args()
    if args.mode == "dir":
        slim_dir(args.folder)
    else:
        slim_tar(args.src, args.dst)


if __name__ == "__main__":
    sys.exit(main())
