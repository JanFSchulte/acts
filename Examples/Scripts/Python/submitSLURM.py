import subprocess
from time import sleep
for i in range(0,500):
	subprocess.call(["sbatch -N1 -n10 --time=4:00:00 acts_tau3mu_submit.sh %d"%i],shell=True)

	sleep(0.5)

