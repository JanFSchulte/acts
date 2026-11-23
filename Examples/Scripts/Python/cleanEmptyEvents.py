import csv

from sys import argv
import os





folder = '/tmp/odd_output_tau3mu_run_%s/'%argv[1]


for i in range(0,2000):


    if not os.path.exists(folder + f'event00000{i:04d}-particles_simulated.csv'): continue

    with open(folder + f'event00000{i:04d}-particles_simulated.csv', mode='r', newline='') as file:
        reader = csv.reader(file)
        row_count = sum(1 for row in reader)
        if row_count == 1:
            # Not every file exists: OBJ output is usually off, and
            # full_chain_odd_tau3mu.py's --muon-system-only slimming (on by
            # default) has already removed empty events and tracker output.
            for suffix in [
                "cells.csv", "hits.csv", "hits.obj", "hits_trajectory.obj",
                "measurements.csv", "measurement-simhit-map.csv",
                "particles.csv", "particles_simulated.csv", "seed.csv",
                "track_parameters_ambi.csv", "track_parameters_ckf.csv",
                "tracks_ambi.csv", "tracks_ckf.csv",
            ]:
                path = folder + f'event00000{i:04d}-' + suffix
                if os.path.exists(path):
                    os.remove(path)
