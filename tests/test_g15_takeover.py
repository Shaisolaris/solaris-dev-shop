"""Do not turn observed assignments into authority over an unobserved population."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'employees/data/data-scientist/experiment_readout.py'
FIX = ROOT / 'examples/capabilities/G15/fixtures/retention-lift'

class PopulationAuthority(unittest.TestCase):
    def result(self, package):
        r = subprocess.run([sys.executable,'-B',str(TOOL),'analyse',str(package),'--json'],capture_output=True,text=True,timeout=30)
        self.assertEqual(r.returncode,0,r.stderr)
        return json.loads(r.stdout)

    def test_missing_population_cannot_allow_causality(self):
        r=self.result(FIX/'package.json')
        self.assertEqual(r['outcome'],'difference_detected')  # still a useful statistical readout
        self.assertFalse(r['claims_allowed']['causal'])
        self.assertTrue(r['claims_allowed']['significance'])
        self.assertIn('no causal claim is allowed',' '.join(r['trace']))

    def test_external_population_control_and_disagreement(self):
        with tempfile.TemporaryDirectory(prefix='solaris-population-')as td:
            d=Path(td)/'fixture';shutil.copytree(FIX,d)
            p=d/'package.json';doc=json.loads(p.read_text())
            # Fixture truth:600+600 single-arm units and6 distinct two-arm units.
            doc['randomization']['expected_units']=1206;p.write_text(json.dumps(doc))
            r=self.result(p)
            self.assertTrue(r['claims_allowed']['causal'])
            self.assertTrue(r['assignment_check']['missing_units_checked'])
            doc['randomization']['expected_units']=1207;p.write_text(json.dumps(doc))
            r=self.result(p)
            self.assertEqual(r['outcome'],'invalid_experiment')
            self.assertFalse(r['claims_allowed']['causal'])
