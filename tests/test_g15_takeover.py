"""Do not turn observed assignments into authority over an unobserved population."""
import json
import importlib.util
import random
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
            self.assertFalse(r['claims_allowed']['causal'])  # known post-assignment cross-arm exclusions
            self.assertIn('multiple-arm units were excluded',' '.join(r['trace']))
            self.assertTrue(r['assignment_check']['missing_units_checked'])
            doc['randomization']['expected_units']=1207;p.write_text(json.dumps(doc))
            r=self.result(p)
            self.assertEqual(r['outcome'],'invalid_experiment')
            self.assertFalse(r['claims_allowed']['causal'])

    def test_complete_clean_randomized_population_can_still_support_the_claim(self):
        spec=importlib.util.spec_from_file_location('root_experiment_generator',ROOT/'examples/capabilities/G15/readout_oracle.py')
        o=importlib.util.module_from_spec(spec);spec.loader.exec_module(o)
        package, assignments, events, truth, contaminated = o.experiment(random.Random(77),n=(600,600),p=(.05,.55),contaminated=0)
        self.assertEqual(package['randomization']['expected_units'],1200)
        self.assertFalse(contaminated)
        with tempfile.TemporaryDirectory(prefix='solaris-clean-experiment-')as td:
            r=self.result(o.write(Path(td)/'fixture',package,assignments,events))
            self.assertTrue(r['claims_allowed']['causal'])
            self.assertTrue(r['claims_allowed']['significance'])
