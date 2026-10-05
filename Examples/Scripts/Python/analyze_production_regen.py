import csv
import glob
import io
import json
import sys
import tarfile
from collections import defaultdict

PROD_DIR = "/depot/cms/private/users/schul105/ACTS/test/acts/Examples/Scripts/Python/production_tau3mu"
TAU_MASS_PDG = 1.77686


def volume_of(gid):
    return (int(gid) >> 56) & 0xFF


def mass(px, py, pz, m):
    e = (px * px + py * py + pz * pz + m * m) ** 0.5
    return e


def process_tar(path, agg):
    t = tarfile.open(path, mode="r:")
    members = t.getmembers()
    by_event = defaultdict(dict)
    n_initial = 0
    for m in members:
        name = m.name.split("/")[-1]
        if name.endswith("-particles_simulated.csv"):
            evt = name.split("-")[0]
            by_event[evt]["particles"] = m
            n_initial += 1
        elif name.endswith("-hits.csv"):
            evt = name.split("-")[0]
            by_event[evt]["hits"] = m

    agg["n_initial_events"] += n_initial

    for evt, d in by_event.items():
        if "particles" not in d:
            continue
        agg["n_nonempty_events"] += 1

        f = t.extractfile(d["particles"])
        reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"))
        muons = {}
        for row in reader:
            if abs(int(row["particle_type"])) == 13 and int(row["particle_id_pv"]) == 1:
                key = (row["particle_id_pv"], row["particle_id_sv"], row["particle_id_part"],
                       row["particle_id_gen"], row["particle_id_subpart"])
                muons[key] = {
                    "px": float(row["px"]), "py": float(row["py"]), "pz": float(row["pz"]),
                    "m": float(row["m"]),
                }
        if len(muons) != 3:
            continue

        agg["n_signal_events"] += 1

        px = sum(mm["px"] for mm in muons.values())
        py = sum(mm["py"] for mm in muons.values())
        pz = sum(mm["pz"] for mm in muons.values())
        e = sum(mass(mm["px"], mm["py"], mm["pz"], mm["m"]) for mm in muons.values())
        tau_mass = (e * e - px * px - py * py - pz * pz) ** 0.5
        agg["tau_mass_list"].append(tau_mass)
        if abs(tau_mass - TAU_MASS_PDG) < 0.001:
            agg["n_pdg_match"] += 1

        evt_pz_sign = "neg" if pz < 0 else "pos"
        agg["event_pz_sign"][evt_pz_sign] += 1

        if "hits" not in d:
            continue
        f2 = t.extractfile(d["hits"])
        reader2 = csv.DictReader(io.TextIOWrapper(f2, encoding="utf-8"))
        hit_counts = defaultdict(lambda: defaultdict(int))
        for row in reader2:
            key = (row["particle_id_pv"], row["particle_id_sv"], row["particle_id_part"],
                   row["particle_id_gen"], row["particle_id_subpart"])
            if key not in muons:
                continue
            vol = volume_of(row["geometry_id"])
            hit_counts[key][vol] += 1

        for key, muon in muons.items():
            pt = (muon["px"] ** 2 + muon["py"] ** 2) ** 0.5
            agg["muon_pt_list"].append(pt)
            pz_sign = "neg" if muon["pz"] < 0 else "pos"
            agg["muon_pz_sign"][pz_sign] += 1
            hc = hit_counts.get(key, {})
            any_hit = False
            for vol in (4, 36, 37):
                n = hc.get(vol, 0)
                if n > 0:
                    any_hit = True
                    agg["hits_by_volume"][vol] += n
                    agg["muon_hit_count_by_vol_sign"][(pz_sign, vol)] += 1
            if any_hit:
                agg["n_muons_with_hit"] += 1
            agg["n_muons_total"] += 1

    t.close()


def main():
    files = sorted(glob.glob(PROD_DIR + "/odd_output_tau3mu_run_*.tar"))
    agg = {
        "n_initial_events": 0,
        "n_nonempty_events": 0,
        "n_signal_events": 0,
        "n_pdg_match": 0,
        "tau_mass_list": [],
        "muon_pt_list": [],
        "event_pz_sign": defaultdict(int),
        "muon_pz_sign": defaultdict(int),
        "hits_by_volume": defaultdict(int),
        "muon_hit_count_by_vol_sign": defaultdict(int),
        "n_muons_with_hit": 0,
        "n_muons_total": 0,
    }
    n_ok = 0
    n_fail = 0
    for i, path in enumerate(files):
        try:
            process_tar(path, agg)
            n_ok += 1
        except Exception as e:
            n_fail += 1
            print(f"FAILED on {path}: {e}", flush=True)
        if (i + 1) % 25 == 0 or (i + 1) == len(files):
            print(f"[{i+1}/{len(files)}] ok={n_ok} fail={n_fail} signal_events_so_far={agg['n_signal_events']}", flush=True)

    tau_masses = agg["tau_mass_list"]
    pts = agg["muon_pt_list"]

    print("\n=== FINAL RESULTS (regenerated production, fixed seeding) ===")
    print("Tar files found:", len(files), " processed OK:", n_ok, " failed:", n_fail)
    print("Total initial events:", agg["n_initial_events"])
    print("Non-empty events:", agg["n_nonempty_events"])
    print("Signal events (exactly 3 truth muons at PV):", agg["n_signal_events"])
    print("Event-level net pz sign:", dict(agg["event_pz_sign"]))
    print("Muon-level pz sign:", dict(agg["muon_pz_sign"]))
    print("Muons with >=1 muon-system hit:", agg["n_muons_with_hit"], "/", agg["n_muons_total"])
    if tau_masses:
        print(f"Tau mass: mean={sum(tau_masses)/len(tau_masses):.4f} min={min(tau_masses):.4f} max={max(tau_masses):.4f}")
    print("Events matching PDG tau mass to <1 MeV:", agg["n_pdg_match"], "/", agg["n_signal_events"])
    if pts:
        print(f"Muon truth pT: mean={sum(pts)/len(pts):.3f} min={min(pts):.3f} max={max(pts):.3f}")
    print("Hits by volume:", dict(sorted(agg["hits_by_volume"].items())))
    print("muon_hit_count_by_vol_sign (pz_sign, vol) -> n_muons:")
    for k in sorted(agg["muon_hit_count_by_vol_sign"]):
        print(" ", k, agg["muon_hit_count_by_vol_sign"][k])

    with open("analyze_production_regen_results.json", "w") as f:
        json.dump({
            "n_initial_events": agg["n_initial_events"],
            "n_nonempty_events": agg["n_nonempty_events"],
            "n_signal_events": agg["n_signal_events"],
            "event_pz_sign": dict(agg["event_pz_sign"]),
            "muon_pz_sign": dict(agg["muon_pz_sign"]),
            "n_muons_with_hit": agg["n_muons_with_hit"],
            "n_muons_total": agg["n_muons_total"],
            "n_pdg_match": agg["n_pdg_match"],
            "hits_by_volume": dict(agg["hits_by_volume"]),
            "muon_hit_count_by_vol_sign": {str(k): v for k, v in agg["muon_hit_count_by_vol_sign"].items()},
        }, f, indent=2)
    print("\nSaved summary to analyze_production_regen_results.json")


if __name__ == "__main__":
    main()
