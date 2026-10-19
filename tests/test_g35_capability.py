"""G35: campaign accounting without live spend (paid-ads-manager campaign_ledger.py, social and CMO hand-offs)."""
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "employees/marketing/paid-ads-manager/campaign_ledger.py"
EX = ROOT / "examples/capabilities/G35"
FIX = EX / "fixtures"
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")


def run(pkg, *extra):
    r = subprocess.run([sys.executable, str(TOOL), "reconcile", str(pkg), "--json"] + list(extra),
                       capture_output=True, text=True, env=ENV, timeout=300)
    return r.returncode, (json.loads(r.stdout) if r.stdout.strip() else None), r.stderr


def camp(rep, cid):
    return next(c for c in rep["campaigns"] if c["id"] == cid)


def figs(rep, cid):
    c = camp(rep, cid)
    return (c["spend"], c["conversions"], c["attributed_revenue"], c["cpa"], c["roas"])


class G35CampaignLedger(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="g35-test-"))
        cls.sept = run(FIX / "september/campaign.json")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def copy(self, name):
        d = self.tmp / ("%s-%s" % (name, self.id().rsplit(".", 1)[-1]))
        shutil.copytree(FIX / name, d)
        return d

    def test_clean_control_exit0_exact(self):
        rc, rep, err = run(FIX / "clean/campaign.json")
        self.assertEqual(rc, 0, err)
        self.assertEqual(rep["status"], "reconciled")
        self.assertEqual(figs(rep, "C-search"), ("30.00", 2, "75.00", "15.00", "2.5000"))
        self.assertEqual([(c["id"], c["status"]) for c in rep["creatives"]], [("K1", "ready_for_human_review")])
        self.assertEqual(rep["finance_tie_out"]["currencies"]["USD"]["difference"], "0.00")

    def test_september_hand_worked_figures(self):
        rc, rep, err = self.sept
        self.assertEqual(rc, 1, err)
        self.assertEqual(figs(rep, "C-search"), ("73.00", 2, "180.00", "36.50", "2.4658"))
        self.assertEqual(figs(rep, "C-social"), ("25.00", 2, "110.00", "12.50", "4.4000"))
        self.assertEqual(figs(rep, "C-eu"), ("8.00", 1, "45.00", "8.00", "5.6250"))
        self.assertEqual((camp(rep, "C-social")["click_conversions"], camp(rep, "C-social")["view_conversions"]), (1, 1))
        self.assertEqual(camp(rep, "C-search")["orders"], ["O1", "O3"])
        ck = rep["checks"]["USD"]
        self.assertEqual((ck["order_value_total"], ck["attributed"], ck["unattributed"]), ("555.00", "290.00", "265.00"))
        self.assertEqual((ck["spend_export_total"], ck["campaign_spend"], ck["unassigned_spend"]), ("102.00", "98.00", "4.00"))
        self.assertTrue(ck["revenue_identity_ok"] and ck["spend_identity_ok"])

    def test_september_findings_named(self):
        rep = self.sept[1]
        self.assertEqual(sorted(f["code"] for f in rep["findings"]), sorted([
            "spend_export_gaps", "spend_for_unknown_campaign", "rejected_touch_rows", "late_conversion_rows",
            "touches_for_unknown_campaign", "conversion_without_order", "over_daily_budget", "spend_outside_flight",
            "order_value_differs_from_recognized_revenue", "creatives_blocked"]))
        f = {x["code"]: x for x in rep["findings"]}
        self.assertEqual(f["over_daily_budget"]["days"], [{"cap": "20.00", "day": "2026-09-05", "spend": "25.00"}])
        self.assertEqual(f["spend_outside_flight"]["days"], ["2026-09-08"])
        self.assertEqual(f["order_value_differs_from_recognized_revenue"]["difference"], "60.00")
        self.assertEqual(f["conversion_without_order"]["examples"][0]["order_id"], "O8")
        self.assertEqual(rep["unattributed"], {"ambiguous_touch": {"USD": {"orders": 1, "value": "25.00"}},
                                               "no_conversion_event": {"USD": {"orders": 1, "value": "200.00"}},
                                               "no_eligible_touch": {"USD": {"orders": 1, "value": "40.00"}}})
        self.assertEqual(rep["reported_value_differs"]["examples"][0]["order_id"], "O2")

    def test_september_creatives(self):
        rep = self.sept[1]
        st = {c["id"]: (c["status"], sorted({r["code"] for r in c["reasons"]})) for c in rep["creatives"]}
        self.assertEqual(st, {"K1": ("held_unverified", []), "K2": ("held_unverified", []),
                              "K3": ("blocked", ["prohibited_claim", "unsupported_number"]),
                              "K4": ("blocked", ["publish_request_refused"]), "K5": ("blocked", ["claim_mismatch"]),
                              "K6": ("blocked", ["material_connection_unknown"])})

    def test_redelivered_and_shuffled_same(self):
        d = self.copy("september")
        for n in ("touches.jsonl", "conversions.jsonl"):
            lines = (d / n).read_text().splitlines()
            (d / n).write_text("\n".join(list(reversed(lines)) + [l for l in lines if l.endswith("}")]) + "\n")
        rc, rep, err = run(d / "campaign.json")
        self.assertEqual(rc, 1, err)
        for cid in ("C-search", "C-social", "C-eu"):
            self.assertEqual(figs(rep, cid), figs(self.sept[1], cid))

    def test_invalid_keeps_previous_report_then_recovers(self):
        d = self.copy("clean")
        out = self.tmp / "out-invalid"
        self.assertEqual(run(d / "campaign.json", "--out", str(out))[0], 0)
        before = (out / "report.json").read_bytes()
        good = (d / "campaign.json").read_text()
        for bad in (good.replace('"300.00"', "300.00"), good.replace('"touches.jsonl"', '"../x.jsonl"'),
                    good.replace('"schema"', '"spend_now": 1, "schema"'), good[:40]):
            (d / "campaign.json").write_text(bad)
            rc, _, err = run(d / "campaign.json", "--out", str(out))
            self.assertEqual(rc, 2, bad[:60])
            self.assertIn("nothing written", err)
            self.assertEqual((out / "report.json").read_bytes(), before)
        (d / "campaign.json").write_text(good)
        self.assertEqual(run(d / "campaign.json", "--out", str(d / "inside"))[0], 2)
        self.assertEqual(run(d / "campaign.json", "--out", str(out))[0], 0)
        self.assertIn("INTERNAL DRAFT", (out / "campaign-brief.md").read_text())

    def test_window_edges(self):
        d = self.copy("clean")
        conv = (d / "conversions.jsonl").read_text()
        # T1 click 09-02T10:00 with a 7-day window; move O1's conversion one second past it
        (d / "conversions.jsonl").write_text(conv.replace('"at": "2026-09-03T10:00:00Z"', '"at": "2026-09-09T10:00:01Z"'))
        (d / "orders.csv").write_text((d / "orders.csv").read_text().replace("O1,50.00,USD,paid,2026-09-03T10:00:00Z", "O1,50.00,USD,paid,2026-09-09T10:00:01Z"))
        rc, rep, _ = run(d / "campaign.json")
        self.assertEqual(camp(rep, "C-search")["conversions"], 1)
        self.assertEqual(rep["unattributed"]["no_eligible_touch"]["USD"]["value"], "50.00")
        (d / "conversions.jsonl").write_text(conv.replace('"at": "2026-09-03T10:00:00Z"', '"at": "2026-09-09T10:00:00Z"'))
        rc, rep, _ = run(d / "campaign.json")
        self.assertEqual(camp(rep, "C-search")["conversions"], 2)

    def test_conversion_before_click_not_credited(self):
        d = self.copy("clean")
        t = (d / "touches.jsonl").read_text().replace('"at": "2026-09-02T10:00:00Z"', '"at": "2026-09-03T10:00:01Z"')
        (d / "touches.jsonl").write_text(t)
        rc, rep, _ = run(d / "campaign.json")
        self.assertEqual(camp(rep, "C-search")["conversions"], 1)

    def test_unseen_edges_flight_currency_window_and_empty_campaign(self):
        d = self.copy("clean")
        pkg = json.loads((d / "campaign.json").read_text())
        pkg["campaigns"][0]["flight_start"] = "2026-09-03"          # T1 (09-02) is now before the flight
        pkg["campaigns"].append({"id": "C-idle", "currency": "USD", "flight_start": "2026-09-01", "flight_end": "2026-09-30",
                                 "budget_total": "10.00", "budget_daily": "5.00", "click_window_days": 7, "view_window_days": 0})
        (d / "campaign.json").write_text(json.dumps(pkg))
        with open(d / "conversions.jsonl", "a") as f:                # a conversion dated before the window
            f.write(json.dumps({"event_id": "E0", "order_id": "O0", "user": "u1", "at": "2026-08-31T23:59:59Z",
                                "loaded_at": "2026-09-01T00:10:00Z", "source": "pixel"}) + "\n")
        o = (d / "orders.csv").read_text().replace("O2,25.00,USD,", "O2,25.00,EUR,")
        (d / "orders.csv").write_text(o)
        rc, rep, err = run(d / "campaign.json")
        self.assertEqual(rc, 1, err)
        self.assertEqual(rep["inputs"]["touches"]["outside_flight"], 1)
        self.assertEqual(rep["inputs"]["conversions"]["outside_window"], 1)
        self.assertEqual(camp(rep, "C-search")["conversions"], 0)
        self.assertEqual((camp(rep, "C-idle")["cpa"], camp(rep, "C-idle")["roas"]), (None, None))
        self.assertEqual(rep["unattributed"]["no_eligible_touch"]["USD"]["value"], "50.00")
        self.assertEqual(rep["unattributed"]["currency_mismatch"]["EUR"]["value"], "25.00")
        codes = {f["code"] for f in rep["findings"]}
        self.assertIn("conversion_currency_mismatch", codes)
        self.assertNotIn("conversion_without_order", codes)

    def test_creative_claims_must_match(self):
        d = self.copy("clean")
        doc = json.loads((d / "creatives.json").read_text())
        k = doc["creatives"][0]
        doc["creatives"].append(dict(k, id="K2", headline=k["headline"].replace("2.5x", "2.6x"),
                                     claims=[dict(k["claims"][0], text="2.6x")] + k["claims"][1:]))
        doc["creatives"].append(dict(k, id="K3", body=k["body"] + " Up 30 percent."))
        doc["creatives"].append(dict(k, id="K4", ad_id="123"))
        (d / "creatives.json").write_text(json.dumps(doc))
        rc, rep, _ = run(d / "campaign.json")
        st = {c["id"]: c["status"] for c in rep["creatives"]}
        self.assertEqual(st, {"K1": "ready_for_human_review", "K2": "blocked", "K3": "blocked", "K4": "blocked"})
        self.assertEqual(rc, 1)

    def fresh_copy(self, name):
        d = Path(tempfile.mkdtemp(dir=str(self.tmp))) / name
        shutil.copytree(FIX / name, d)
        return d

    def _edit_json(self, path, fn):
        d = json.loads(path.read_text())
        fn(d)
        path.write_text(json.dumps(d))

    def test_r2_mixed_windows_and_cutoffs_refused(self):
        # M35 P2-1 (validator finding; fix generalized from its proposed patch): both G13 contracts must carry
        # the package window and as_of, or periods and cutoffs mix silently into spend, CPA and ROAS.
        cases = [("spend-contract.json", lambda d: d["window"].update(start="2026-08-01T00:00:00Z"), "spend contract window"),
                 ("spend-contract.json", lambda d: d.update(as_of="2026-10-20T00:00:00Z"), "spend contract as_of"),
                 ("spend-contract.json", lambda d: d.pop("as_of"), "spend contract as_of"),
                 ("orders-contract.json", lambda d: d.update(as_of="2026-10-05T00:00:00Z"), "orders contract as_of"),
                 ("orders-contract.json", lambda d: d["window"].update(end="2026-10-02T00:00:00Z"), "orders contract window")]
        for name, fn, msg in cases:
            d = self.fresh_copy("clean")
            self._edit_json(d / name, fn)
            rc, rep, err = run(d / "campaign.json")
            self.assertEqual(rc, 2, (name, msg, err))
            self.assertIn(msg, err)
        d = self.fresh_copy("clean")  # same instant written with another offset is the same basis
        self._edit_json(d / "spend-contract.json", lambda d: d.update(as_of="2026-10-01T17:00:00-07:00"))
        self.assertEqual(run(d / "campaign.json")[0], 0)

    def test_r2_cpa_null_without_spend(self):
        # M35 P3-1: conversions but no spend gives CPA null (and ROAS null), never 0.00.
        d = self.fresh_copy("clean")
        lines = (d / "spend.csv").read_text().splitlines()
        (d / "spend.csv").write_text(lines[0] + "\n")
        ctl = d / "spend-contract.json"
        c = json.loads(ctl.read_text())
        if c.get("controls"):
            cf = d / c["controls"]["file"]
            cf.write_text("file,rows,sum\nspend.csv,0,0.00\n")
        rc, rep, err = run(d / "campaign.json")
        self.assertIsNotNone(rep, err)
        sp, n, rev, cpa, roas = figs(rep, "C-search")
        self.assertEqual((sp, n, cpa, roas), ("0.00", 2, None, None))

    def test_r2_prohibited_wording_dash_and_width_variants(self):
        # M35 P4-1: dash variants, NFKC width forms and case cannot hide a prohibited phrase.
        for head in ["Risk\u2011free search", "Risk\u2013free search", "RISK\u2212FREE search", "Risk\u00adfree search",
                     "\uff27\uff35\uff21\uff32\uff21\uff2e\uff34\uff25\uff25\uff24 returns", "Risk  free search"]:
            d = self.fresh_copy("clean")
            self._edit_json(d / "creatives.json", lambda c: c["creatives"][0].update(headline=head))
            rc, rep, err = run(d / "campaign.json")
            k = rep["creatives"][0]
            self.assertNotEqual(k["status"], "ready_for_human_review", head)
            self.assertIn("prohibited_claim", json.dumps(k), head)

    def test_oracle_accepts_tool_and_rejects_controls(self):
        def oracle(*tool):
            r = subprocess.run([sys.executable, str(EX / "campaign_oracle.py"), "--seeds", "1", "--"] + list(tool),
                               capture_output=True, text=True, env=ENV, timeout=600)
            return r.stdout.strip().splitlines()[-1]
        self.assertEqual(oracle(sys.executable, str(TOOL)), "ACCEPTED 12/12")
        self.assertTrue(oracle(sys.executable, str(EX / "naive_ledger.py")).startswith("REJECTED"))
        self.assertTrue(oracle(sys.executable, str(EX / "noop_ledger.py")).startswith("REJECTED"))

    def test_contract_and_docs_wired(self):
        c = json.loads((ROOT / "employees/marketing/paid-ads-manager/capability.contract.json").read_text())
        self.assertIn("campaign_ledger.py", c["dependencies"]["scripts"])
        self.assertIn("campaign-accounting.md", c["dependencies"]["references"])
        doc = (ROOT / "employees/marketing/paid-ads-manager/campaign-accounting.md").read_text()
        for word in ("Attribution", "budget", "never", "G13", "G14"):
            self.assertIn(word, doc)
        for role in ("marketing/social-media-manager", "leadership/cmo"):
            self.assertIn("campaign_ledger.py", (ROOT / "employees" / role / "SKILL.md").read_text())

    def test_tool_has_no_network_or_publish_code(self):
        src = TOOL.read_text()
        for bad in ("import socket", "urllib", "http.client", "requests", "smtplib"):
            self.assertNotIn(bad, src)


if __name__ == "__main__":
    unittest.main()
