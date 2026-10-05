#!/bin/sh
#SBATCH --job-name=ACTS_tau3mu_largeseed #Job name
#SBATCH --mail-type=FAIL # Mail events (NONE, BEGIN, END, FAIL, ALL)
#SBATCH --mail-user=schul105@purdue.edu # Where to send mail
#SBATCH --account=cms-express
#SBATCH --output=/home/schul105/depot/ACTS/test/acts/Examples/Scripts/Python/slurm_output/largeseed-%A.out	# Name output file

NJOB=$1
# NJOB is offset into the 9000s so it never collides with the main production's
# job-index/output-folder range (0-500); the ACTUAL random seed passed to Pythia/ACTS
# is a large, well-separated value derived from it, to test whether proximity-to-zero
# seeds (as used in the main production, --rs = job index 0..500) cause a bias.
SEED=$((999999000 + NJOB * 104729))

pwd; date; hostname

#   Confirmatory test: same physics config as the main tau3mu production, but with a
#   large, well-separated random seed instead of the small sequential job index, to
#   check whether the muon forward/backward asymmetry is a std::mt19937 small-seed
#   artifact rather than a real physics effect.

mydir=/home/schul105/depot/ACTS/test/acts/Examples/Scripts/Python/
cd $mydir
source /cvmfs/sft.cern.ch/lcg/views/LCG_107/x86_64-el8-gcc11-opt/setup.sh
module load gcc/14.1.0
source ../../../build/python/setup.sh
source ../../../build/thirdparty/OpenDataDetector/this_odd.sh

echo "Working in "`pwd`
echo "Will run Tau3Mu Generation with ACTS for job = " ${NJOB} " seed = " ${SEED}

python3.11 full_chain_odd_tau3mu.py --ttbar --events 2000 --rs ${SEED} --output /tmp/odd_output_tau3mu_run_${NJOB}

python3.11 cleanEmptyEvents.py ${NJOB}

mkdir -p largeseed_test
tar -cf largeseed_test/odd_output_tau3mu_largeseed_${NJOB}.tar -C /tmp odd_output_tau3mu_run_${NJOB}

rm -rf /tmp/odd_output_tau3mu_run_${NJOB}

date
