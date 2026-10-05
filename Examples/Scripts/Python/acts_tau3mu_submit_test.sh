#!/bin/sh
#SBATCH --job-name=ACTS_tau3mu #Job name
#SBATCH --mail-type=FAIL # Mail events (NONE, BEGIN, END, FAIL, ALL)
#SBATCH --mail-user=schul105@purdue.edu # Where to send mail
#SBATCH --account=cms-express
#SBATCH --output=/home/schul105/depot/ACTS/test/acts/Examples/Scripts/Python/slurm_output/test-%A.out	# Name output file

NJOB=$1

# Derive the Pythia/ACTS random seed from the job index via a 32-bit integer
# hash (Murmur3 fmix32) instead of passing NJOB directly. RandomNumbers::generateSeed
# does `seed = base_seed + eventNumber`, so sequential small job indices (0..N) fed
# straight into std::mt19937 produce correlated, not independent, event streams across
# jobs -- this showed up as a ~2:1 negative/positive-z muon asymmetry across the
# production. Hashing first spreads job indices across the full 32-bit seed space.
h=$(( NJOB ^ 0x9E3779B9 ))
h=$(( (h ^ (h >> 16)) & 0xFFFFFFFF ))
h=$(( (h * 0x85ebca6b) & 0xFFFFFFFF ))
h=$(( (h ^ (h >> 13)) & 0xFFFFFFFF ))
h=$(( (h * 0xc2b2ae35) & 0xFFFFFFFF ))
SEED=$(( (h ^ (h >> 16)) & 0xFFFFFFFF ))

pwd; date; hostname

#   Tau3Mu production with the muon-system-fixed ACTS/OpenDataDetector build
#   $1 == input parameter (job index, used for output naming); SEED (derived above) is
#   the actual random seed passed to the generator.

mydir=/home/schul105/depot/ACTS/test/acts/Examples/Scripts/Python/
cd $mydir
source /cvmfs/sft.cern.ch/lcg/views/LCG_107/x86_64-el8-gcc11-opt/setup.sh
module load gcc/14.1.0
source ../../../build/python/setup.sh
source ../../../build/thirdparty/OpenDataDetector/this_odd.sh

echo "Working in "`pwd`

echo "Will run Tau3Mu Generation with ACTS for job = " ${NJOB} " seed = " ${SEED}

python3.11 full_chain_odd_tau3mu.py --ttbar --events 2000 --rs ${SEED} --output /tmp/odd_output_tau3mu_run_${NJOB} --no-output-root --no-output-obj

python3.11 cleanEmptyEvents.py ${NJOB}

tar -cf production_tau3mu/odd_output_tau3mu_run_${NJOB}.tar -C /tmp odd_output_tau3mu_run_${NJOB}

rm -rf /tmp/odd_output_tau3mu_run_${NJOB}

date
