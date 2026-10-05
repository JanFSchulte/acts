#!/bin/bash
cd /depot/cms/private/users/schul105/ACTS/test/acts/Examples/Scripts/Python

# Wait until all submissions have even been queued (submitSLURM_regen.py finishes fast)
while pgrep -f "submitSLURM_regen.py" > /dev/null; do
  sleep 10
done

# Wait until no ACTS_tau3mu jobs remain in the queue (running or pending)
while squeue -u schul105 -n ACTS_tau3mu -h | grep -q .; do
  sleep 60
done

echo "All production jobs finished at $(date)" >> regen_production.log

source /cvmfs/sft.cern.ch/lcg/views/LCG_107/x86_64-el8-gcc11-opt/setup.sh
module load gcc/14.1.0 2>> regen_production.log
source ../../../build/python/setup.sh

python3.11 analyze_production_regen.py >> regen_production.log 2>&1

echo "Analysis finished at $(date)" >> regen_production.log
