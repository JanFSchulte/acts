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
            os.remove(folder + f'event00000{i:04d}-cells.csv')
            os.remove(folder + f'event00000{i:04d}-hits.csv')
            os.remove(folder + f'event00000{i:04d}-hits.obj')
            os.remove(folder + f'event00000{i:04d}-hits_trajectory.obj')
            os.remove(folder + f'event00000{i:04d}-measurements.csv')
            os.remove(folder + f'event00000{i:04d}-measurement-simhit-map.csv')
            os.remove(folder + f'event00000{i:04d}-particles.csv')
            os.remove(folder + f'event00000{i:04d}-particles_simulated.csv')
            os.remove(folder + f'event00000{i:04d}-seed.csv')
            os.remove(folder + f'event00000{i:04d}-track_parameters_ambi.csv')
            os.remove(folder + f'event00000{i:04d}-track_parameters_ckf.csv')
            os.remove(folder + f'event00000{i:04d}-tracks_ambi.csv')
            os.remove(folder + f'event00000{i:04d}-tracks_ckf.csv')


