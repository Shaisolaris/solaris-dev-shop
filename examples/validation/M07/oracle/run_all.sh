#!/bin/zsh
# M07 runner (Grok self-validation). Usage: zsh run_all.sh ORACLE_DIR RESULTS TREE PY...
O=$1; R=$2; C=$3; shift 3; mkdir -p $R/builder $R/oracle $R/controls
for py in $@; do v=$($py -c 'import sys;print(sys.version.split()[0])')
  ( cd $C && PYTHONDONTWRITEBYTECODE=1 $py -m unittest tests.test_g07_capability > $R/builder/g07-tests-$v.txt 2>&1; echo "rc $?" >> $R/builder/g07-tests-$v.txt
    PYTHONDONTWRITEBYTECODE=1 $py -m unittest discover -s tests > $R/builder/full-suite-$v.txt 2>&1; echo "rc $?" >> $R/builder/full-suite-$v.txt
    PYTHONDONTWRITEBYTECODE=1 $py examples/capabilities/G07/registry_oracle.py > $R/builder/builder-oracle-$v.txt 2>&1; echo "rc $?" >> $R/builder/builder-oracle-$v.txt )
  $py $O/m07_oracle.py $C $R/oracle/oracle-$v.json > $R/oracle/oracle-$v.txt 2>&1
done
py=$1; for c in naive noop; do $py $O/m07_oracle.py $C --tool $C/examples/capabilities/G07/${c}_registry.py $R/controls/$c.json > $R/controls/$c.txt 2>&1; done
echo ALL-DONE
