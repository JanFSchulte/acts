#!/usr/bin/env python3
"""Slim ODD tau3mu / minimum-bias output down to what muon-system studies need.

Per event this keeps
  - hits.csv rows in the muon-system volumes (MUON_VOLUMES), byte-for-byte
    as written (same columns, same precision), and
  - particles.csv / particles_simulated.csv rows for particles that left a
    hit there, plus every particle of the signal vertex (SIGNAL_PV), which
    downstream code uses to find the tau3mu muons,
and drops the tracker-only digitization outputs (measurements, cells) and
the reconstruction outputs (seeds, tracks). Anything else (timing.csv, ...)
is kept unchanged. Events whose particles_simulated.csv is empty (rejected by
the tau3mu filter) are dropped altogether. Standard library only, so it runs
under the LCG view's python3.11 on a worker as well as anywhere else.

full_chain_odd_tau3mu.py and full_chain_odd_minbias.py call slim_dir() on
their own output unless run with --no-muon-system-only. From the command
line:

    muon_system_slim.py dir <output_dir>
        slim an output directory in place

    muon_system_slim.py tar <input.tar> <output.tar.gz>
        stream an existing production tar into a slimmed, gzipped one; this
        also drops OBJ and ROOT files, which hold every volume
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

DIGI_SUFFIXES = (
    "-cells.csv",
    "-measurements.csv",
    "-measurement-simhit-map.csv",
)
RECO_SUFFIXES = (
    "-seed.csv",
    "-tracks_ckf.csv",
    "-tracks_ambi.csv",
    "-track_parameters_ckf.csv",
    "-track_parameters_ambi.csv",
)
VIS_SUFFIXES = (".obj", ".root")
HITS_SUFFIX = "-hits.csv"
PARTICLE_SUFFIXES = ("-particles.csv", "-particles_simulated.csv")
SIMULATED_SUFFIX = "-particles_simulated.csv"
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


def empty_events(folder, names):
    empty = set()
    for name in names:
        if name.endswith(SIMULATED_SUFFIX):
            with open(os.path.join(folder, name)) as fh:
                fh.readline()
                if not fh.readline():
                    empty.add(event_of(name))
    return empty


def slim_dir(folder, keep_reco=False):
    """Slim an output directory in place. OBJ and ROOT files are left alone;
    their own --output-obj/--output-root switches decide whether they exist.
    """
    folder = str(folder)
    drop = DIGI_SUFFIXES + (() if keep_reco else RECO_SUFFIXES)
    names = sorted(os.listdir(folder))
    empty = empty_events(folder, names)
    keys_by_event = {}
    n_in = n_out = 0
    for name in names:
        path = os.path.join(folder, name)
        if name.startswith("event") and event_of(name) in empty:
            os.remove(path)
        elif name.endswith(drop):
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
        if name.endswith(PARTICLE_SUFFIXES) and event_of(name) not in empty:
            path = os.path.join(folder, name)
            with open(path) as fh:
                kept = filter_particles(fh.read(), keys_by_event.get(event_of(name), set()))
            with open(path, "w") as fh:
                fh.write(kept)
    print(
        f"muon_system_slim: kept {len(keys_by_event)} events "
        f"(dropped {len(empty)} empty), {n_out}/{n_in} hits"
    )


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
    drop = DIGI_SUFFIXES + RECO_SUFFIXES + VIS_SUFFIXES
    tmp = dst + ".part"
    keys_by_event = {}
    pending = []
    n_in = n_out = 0
    with tarfile.open(src, "r|") as tin, tarfile.open(tmp, "w:gz") as tout:
        for m in tin:
            if not m.isfile():
                tout.addfile(m)
            elif m.name.endswith(drop):
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
    print(f"muon_system_slim: {src} -> {dst}: {len(keys_by_event)} events, kept {n_out}/{n_in} hits")


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
