"""G37: privacy inventory, retention and request handling on existing roles (compliance-auditor, legal-advisor)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "employees/legal-compliance/compliance-auditor/privacy_inventory.py"
EX = ROOT / "examples/capabilities/G37"
FIX = EX / "fixtures"
ENV = dict({name: os.environ[name] for name in (
               'PATH', 'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'TMPDIR',
               'TMP', 'TEMP', 'SystemRoot', 'SYSTEMROOT', 'SystemDrive', 'COMSPEC',
               'ComSpec', 'PATHEXT', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ',
               'PYTHONUTF8', 'PYTHONIOENCODING', 'PYTHONNOUSERSITE', 'PYTHONSAFEPATH', 'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL',
               'GIT_CONFIG_SYSTEM', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'CI',
               'GITHUB_ACTIONS',
           ) if name in os.environ}, PYTHONDONTWRITEBYTECODE="1")


def run(pkg, *extra):
    r = subprocess.run([sys.executable, str(TOOL), "review", str(pkg), "--json"] + list(extra),
                       capture_output=True, text=True, env=ENV, timeout=300)
    return r.returncode, (json.loads(r.stdout) if r.stdout.strip() else None), r.stderr


def reqs(rep):
    return {r["request_id"]: r for r in rep["requests"]}


def codes(rep):
    return sorted(f["code"] for f in rep["findings"])


class G37PrivacyInventory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="g37-test-"))
        cls.sept = run(FIX / "september/package.json")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def copy(self, name):
        d = self.tmp / ("%s-%s" % (name, self.id().rsplit(".", 1)[-1]))
        shutil.copytree(FIX / name, d)
        return d

    def test_clean_control(self):
        rc, rep, err = run(FIX / "clean/package.json")
        self.assertEqual(rc, 0, err)
        self.assertEqual(rep["status"], "complete")
        r = reqs(rep)["R1"]
        self.assertEqual(r["status"], "access_package_ready_for_review")
        self.assertEqual(sorted((x["file"], x["line"]) for x in r["records"]), [("customers.csv", 2), ("orders.csv", 2), ("orders.csv", 4)])
        self.assertEqual(r["access_package"][0]["values"].get("customer_id"), "K1")
        self.assertNotIn("order_id", r["access_package"][0]["values"])   # not personal, not in the package

    def test_september_findings(self):
        rc, rep, err = self.sept
        self.assertEqual(rc, 1, err)
        self.assertEqual(codes(rep), sorted(["flow_to_undeclared_system", "unmapped_field", "stale_inventory_entry",
                                             "retention_anchor_unreadable", "rejected_request_rows", "conflicting_request_ids",
                                             "closed_late", "overdue_request", "unknown_jurisdiction_clock"]))
        f = {x["code"]: x for x in rep["findings"]}
        self.assertEqual((f["unmapped_field"]["field"], f["unmapped_field"]["ignored_by_g13"]), ("birth_date", True))
        self.assertEqual(f["conflicting_request_ids"]["ids"], ["R7"])
        self.assertEqual(f["retention_anchor_unreadable"]["lines"], [6])

    def test_retention_due(self):
        rep = self.sept[1]
        due = {r["table"]: [(d["line"], d["subject"], d["expired_on"]) for d in r["due"]] for r in rep["retention"]}
        self.assertEqual(due, {"orders.csv": [(6, "K9", "2025-04-29")], "customers.csv": [(6, "K9", "2026-01-14")],
                               "tickets.csv": [(2, "K2", "2026-06-01"), (5, "K9", "2025-03-01")]})

    def test_requests_traced(self):
        R = reqs(self.sept[1])
        self.assertEqual(R["R4"]["due"], "2026-02-28T09:00:00+00:00")     # Jan 31 + one month clamps to Feb 28
        self.assertEqual(R["R2"]["due"], "2026-09-15T09:00:00+00:00")     # 45 days
        self.assertEqual(sorted((x["file"], x["line"]) for x in R["R2"]["retain_pending_review"]), [("orders.csv", 3), ("orders.csv", 4)])
        self.assertEqual(R["R2"]["propagate_to"], ["cfo-books", "crm-export", "helpdesk", "warehouse"])
        self.assertEqual(R["R5"]["status"], "no_records_found")
        self.assertIsNone(R["R6"]["due"])
        self.assertEqual(R["R4"]["fields"], ["amount", "contact", "customer_id", "event_time", "name", "region"])
        self.assertNotIn("R7", R)
        self.assertNotIn("R8", R)

    def test_unverified_request_discloses_nothing(self):
        out = self.tmp / "out-unverified"
        r = subprocess.run([sys.executable, str(TOOL), "review", str(FIX / "september/package.json"), "--json", "--out", str(out)],
                           capture_output=True, text=True, env=ENV)
        r3 = reqs(json.loads(r.stdout))["R3"]
        self.assertEqual(r3["status"], "awaiting_identity_verification")
        self.assertNotIn("records", r3)
        blob = r.stdout + (out / "report.json").read_text() + (out / "handoff.md").read_text()
        for s in ("Synthetic Person K3", "contact-token-K3", "1979-07-07"):
            self.assertNotIn(s, blob)

    def test_qualified_review_visible(self):
        rep = self.sept[1]
        why = " ".join(q["why"] for q in rep["qualified_review"])
        for s in ("tickets.csv.body", "hold_for_review", "R2", "BR-LGPD", "EU-GDPR", "US-CA-CCPA"):
            self.assertIn(s, why)
        self.assertIn("Not legal advice", rep["not_legal_advice"])
        self.assertTrue(all(o["refs"] for o in rep["obligations"]))
        self.assertIn("qualified", {o["review"] for o in rep["obligations"]})

    def test_drift_unseen_column(self):
        d = self.copy("clean")
        p = d / "data/customers.csv"
        lines = p.read_text().splitlines()
        p.write_text("\n".join([lines[0] + ",loyalty_tier"] + [l + ",gold" for l in lines[1:]]) + "\n")
        rc, rep, _ = run(d / "package.json")
        self.assertEqual(rc, 1)
        self.assertEqual([(f["code"], f["field"]) for f in rep["findings"]], [("unmapped_field", "loyalty_tier")])

    def test_missing_retention_and_subject_key(self):
        d = self.copy("clean")
        inv = json.loads((d / "inventory.json").read_text())
        del inv["tables"]["customers.csv"]["retention"]
        del inv["tables"]["orders.csv"]["subject_key"]
        inv["tables"]["orders.csv"]["fields"]["amount"].pop("basis")
        (d / "inventory.json").write_text(json.dumps(inv))
        rc, rep, _ = run(d / "package.json")
        self.assertEqual(codes(rep), ["personal_field_without_purpose_or_basis", "personal_table_without_retention",
                                      "personal_table_without_subject_key"])

    def test_unseen_requests_and_inventory_edges(self):
        d = self.copy("clean")
        with open(d / "requests.jsonl", "a") as f:
            f.write(json.dumps({"request_id": "R2", "type": "access", "subject": "K2", "received_at": "2026-03-31T09:00:00Z",
                                "identity_verified": True, "jurisdiction": "EU-GDPR", "closed_at": "2026-04-30T09:00:00Z"}) + "\n")
            f.write(json.dumps({"request_id": "R3", "type": "access", "subject": "K2", "received_at": "2026-09-30T09:00:00Z",
                                "identity_verified": "yes", "jurisdiction": "EU-GDPR"}) + "\n")
        inv = json.loads((d / "inventory.json").read_text())
        inv["tables"]["archive.csv"] = {"fields": {}}
        inv["tables"]["customers.csv"]["subject_key"] = "account_ref"
        (d / "inventory.json").write_text(json.dumps(inv))
        rc, rep, _ = run(d / "package.json")
        R = reqs(rep)
        self.assertEqual(R["R2"]["due"], "2026-04-30T09:00:00+00:00")     # Mar 31 + one month = Apr 30, closed on time
        self.assertNotIn("R3", R)                                          # identity_verified must be a boolean
        self.assertEqual(codes(rep), ["inventoried_table_not_in_data", "rejected_request_rows", "subject_key_not_in_data"])
        pk = json.loads((d / "package.json").read_text())
        pk["clocks"]["US-CA-CCPA"]["source"] = "  "                       # a blank source is no source
        (d / "package.json").write_text(json.dumps(pk))
        self.assertEqual(run(d / "package.json")[0], 2)
        del pk["clocks"]["US-CA-CCPA"]["source"]
        (d / "package.json").write_text(json.dumps(pk))
        self.assertEqual(run(d / "package.json")[0], 2)

    def test_invalid_keeps_previous_and_recovers(self):
        d = self.copy("clean")
        out = self.tmp / "out-invalid"
        self.assertEqual(run(d / "package.json", "--out", str(out))[0], 0)
        before = (out / "report.json").read_bytes()
        good = (d / "package.json").read_text()
        for bad in (good.replace('"inventory.json"', '"../x.json"'), good.replace('"days": 45', '"days": 45.5'),
                    good.replace('"schema"', '"delete_now": 1, "schema"'), good[:20]):
            (d / "package.json").write_text(bad)
            rc, _, err = run(d / "package.json", "--out", str(out))
            self.assertEqual(rc, 2, bad[:50])
            self.assertIn("nothing written", err)
            self.assertEqual((out / "report.json").read_bytes(), before)
        (d / "package.json").write_text(good)
        self.assertEqual(run(d / "package.json", "--out", str(d / "inside"))[0], 2)
        self.assertEqual(run(d / "package.json", "--out", str(out))[0], 0)
        self.assertIn("Not legal advice", (out / "handoff.md").read_text())

    def test_oracle_accepts_tool_rejects_controls(self):
        def oracle(*tool):
            r = subprocess.run([sys.executable, str(EX / "privacy_oracle.py"), "--seeds", "1", "--"] + list(tool),
                               capture_output=True, text=True, env=ENV, timeout=600)
            return r.stdout.strip().splitlines()[-1]
        self.assertEqual(oracle(sys.executable, str(TOOL)), "ACCEPTED 9/9")
        self.assertTrue(oracle(sys.executable, str(EX / "naive_inventory.py")).startswith("REJECTED"))
        self.assertTrue(oracle(sys.executable, str(EX / "noop_inventory.py")).startswith("REJECTED"))

    def test_wired_into_existing_roles_without_a_new_role(self):
        c = json.loads((ROOT / "employees/legal-compliance/compliance-auditor/capability.contract.json").read_text())
        self.assertIn("privacy_inventory.py", c["dependencies"]["scripts"])
        self.assertIn("privacy-inventory.md", c["dependencies"]["references"])
        self.assertIn("privacy_inventory.py", (ROOT / "employees/legal-compliance/legal-advisor/SKILL.md").read_text())
        self.assertFalse((ROOT / "employees/legal-compliance/data-privacy-officer").exists())

    def test_tool_never_deletes_or_sends(self):
        src = TOOL.read_text()
        for bad in ("os.remove", "unlink(p", "shutil.rmtree", "import socket", "urllib", "smtplib", "requests."):
            self.assertNotIn(bad, src)


if __name__ == "__main__":
    unittest.main()
