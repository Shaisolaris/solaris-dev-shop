#!/usr/bin/env python3
"""Naive control: the real release_candidate.py with two common shortcuts. It takes the queue's own
status as the acceptance (so a candidate that moved after review still counts) and skips the metadata
reconciliation. Must fail the G41 oracle."""
import importlib.util, sys
from pathlib import Path
P = Path(__file__).resolve().parents[3] / "employees/quality-security/assurance/release_candidate.py"
spec = importlib.util.spec_from_file_location("g41_naive", str(P))
m = importlib.util.module_from_spec(spec)
sys.dont_write_bytecode = True
spec.loader.exec_module(m)


def disposition(gid, status, acc, cand, repo, use_git):
    if status in m.EXCLUDED:
        return {"id": gid, "queue_status": status, "disposition": "excluded"}
    return {"id": gid, "queue_status": status, "disposition": "accepted" if status == "accepted" else "candidate_only"}


_meta = m.metadata


def metadata(repo):
    d = _meta(repo)
    d["problems"] = []
    return d


m.disposition = disposition
m.metadata = metadata
if __name__ == "__main__":
    sys.exit(m.main())
