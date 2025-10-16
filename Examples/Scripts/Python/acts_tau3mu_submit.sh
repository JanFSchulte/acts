#!/bin/sh
#SBATCH --job-name=ACTS #Job name
#SBATCH --mail-type=FAIL # Mail events (NONE, BEGIN, END, FAIL, ALL)
#SBATCH --mail-user=schul105@purdue.edu # Where to send mail	
#SBATCH --account=cms-express
#SBATCH --output=/home/schul105/depot/ACTS/clean/acts/Examples/Scripts/Python/slurm_output/test-%A.out	# Name output file 

NJOB=$1

pwd; date; hostname


#   Run fewzz job  DY 1D in M   PI bkg
#   $1 == input parameter (working directory)

mydir=/home/schul105/depot/ACTS/clean/acts/Examples/Scripts/Python/
cd $mydir
source /cvmfs/sft.cern.ch/lcg/views/LCG_107/x86_64-el8-gcc11-opt/setup.sh
module load gcc/14.1.0
source ../../../build/python/setup.sh

echo "Working in "`pwd`

echo "Will run Tau3Mu Generation with ACTS for job = " ${NJOB}

python full_chain_odd_tau3mu.py --ttbar --events 2000 --rs ${NJOB} --output /tmp/odd_output_tau3mu_run_${NJOB} 

python cleanEmptyEvents.py ${NJOB}

tar -cvf odd_output_tau3mu_run_${NJOB}.tar /tmp/odd_output_tau3mu_run_${NJOB}

date

