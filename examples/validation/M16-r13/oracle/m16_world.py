"""M16 unseen worlds (Grok self-validation, written without reading the G16 fixtures' text).

1. Brackwater allotments: a hand-written snapshot v1 and a changed v2, with questions whose
   expected answers were worked out by hand from the sentences below.
2. A seeded bus-route generator (routes R1..Rn, stops with two-word names) for unseen seeds
   and scale, with sibling-route and wrong-stop traps.
All text is synthetic. Offsets are code points into the decoded file.
"""
import json
import random
from pathlib import Path

V1 = {
    "plots.md": "# Plot fees (Brackwater Soci\u00e9t\u00e9)\n\n"
                "A full plot costs 64 pounds per season. A half plot costs 38 pounds per season.\n"
                "Plot holders must not light bonfires between April and September.\n"
                "Hosepipes are not allowed on the Eastside site.\n"
                "Each plot holder may keep up to 6 hens.\n",
    "water.md": "# Water\n\n"
                "Water troughs at Westfield are refilled every Tuesday.\n"
                "The Westfield site has 12 troughs.\n"
                "Rainwater butts cost 22 pounds from the society shop.\n",
    "waiting.md": "# Waiting list\n\n"
                  "The Eastside waiting list is currently about 18 months long.\n"
                  "Applicants must live within 3 miles of the site they apply for.\n",
    "shed-2025.md": "# Shed permits 2025\n\nA shed permit costs 15 pounds a year.\n",
    "shed-2026.md": "# Shed permits 2026\n\nA shed permit costs 20 pounds a year.\n",
}

V2 = dict(V1)
V2["plots.md"] = ("# Plot fees (Brackwater Soci\u00e9t\u00e9)\n\n"
                  "Fees are reviewed every March by the committee.\n"
                  "A full plot costs 70 pounds per season. A half plot costs 38 pounds per season.\n"
                  "Plot holders must not light bonfires between April and September.\n"
                  "Hosepipes are not allowed on the Eastside site.\n"
                  "Each plot holder may keep up to 6 hens.\n")
del V2["water.md"]
V2["water-and-shop.md"] = ("# Water and shop\n\n"
                           "Water troughs at Westfield are refilled every Thursday.\n"
                           "The Westfield site has 12 troughs.\n"
                           "Rainwater butts cost 22 pounds from the society shop.\n")


def q(i, text, answerable, facts=(), docs=()):
    e = {"answerable": answerable}
    if answerable:
        e.update(facts=list(facts), support_docs=list(docs))
    return {"id": f"b{i:02d}", "question": text, "expect": e}


QV1 = [
    q(1, "How much does a full plot cost per season?", True, ["64 pounds"], ["plots.md"]),
    q(2, "How much does a half plot cost per season?", True, ["38 pounds"], ["plots.md"]),
    q(3, "How many hens may each plot holder keep?", True, ["6 hens"], ["plots.md"]),
    q(4, "How many troughs does the Westfield site have?", True, ["12 troughs"], ["water.md"]),
    q(5, "When are the Westfield water troughs refilled?", True, ["Tuesday"], ["water.md"]),
    q(6, "How long is the Eastside waiting list?", True, ["18 months"], ["waiting.md"]),
    q(7, "How far from the site must applicants live?", True, ["3 miles"], ["waiting.md"]),
    q(8, "How much do rainwater butts cost?", True, ["22 pounds"], ["water.md"]),
    q(9, "How many troughs does the Northgate site have?", False),        # site not in the snapshot
    q(10, "How much does a shed permit cost?", False),                     # 2025 and 2026 disagree
    q(11, "What is the phone number of the society shop?", False),         # no phone number anywhere
    q(12, "How many plots does the Eastside site have?", False),           # never stated
]
QV2 = [dict(x, expect=dict(x["expect"])) for x in QV1]
QV2[0]["expect"].update(facts=["70 pounds"])
for i in (3, 4, 7):
    QV2[i]["expect"].update(support_docs=["water-and-shop.md"])
QV2[4]["expect"].update(facts=["Thursday"])


def write_snapshot(d: Path, docs: dict) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    for n, t in docs.items():
        (d / n).write_bytes(t.encode("utf-8"))
    return d


def write_questions(p: Path, qs) -> Path:
    p.write_text("".join(json.dumps(x, sort_keys=True) + "\n" for x in qs))
    return p


SYL = ["al", "der", "bri", "ch", "cor", "ven", "dal", "mere", "fen", "wick", "gar", "ston", "hol", "lin", "mar",
       "ket", "nor", "ton", "pel", "ham", "quin", "rey", "sal", "ford", "tam", "worth", "ul", "by", "ves", "ley"]


def _name(rng):
    return (rng.choice(SYL) + rng.choice(SYL)).capitalize() + " " + rng.choice(
        ["Cross", "Hill", "Green", "Quay", "Gate", "Row", "Park", "Yard"])


def bus_world(seed: int, routes: int):
    """Return (docs, questions, truth). Route Rk stops at 2 stops; traps: missing route, wrong stop."""
    rng = random.Random(seed)
    stops = sorted({_name(rng) for _ in range(routes * 3)})
    docs, qs, truth = {}, [], {}
    used = {}
    for k in range(1, routes + 1):
        a, b = rng.sample(stops, 2)
        fa, fb, dur = rng.randint(4, 40), rng.randint(4, 40), rng.randint(11, 95)
        used[k] = (a, b)
        docs[f"route-r{k}.md"] = (f"# Route R{k}\n\n"
                                  f"Route R{k} departs {a} every {fa} minutes. Route R{k} departs {b} every {fb} minutes.\n"
                                  f"The R{k} journey from end to end takes {dur} minutes.\n")
        truth[k] = (a, fa, b, fb, dur)
    n = 0
    for k in range(1, routes + 1):
        a, fa, b, fb, dur = truth[k]
        for text, fact in ((f"How often does route R{k} depart from {a}?", f"every {fa} minutes"),
                           (f"How long does the R{k} journey from end to end take?", f"{dur} minutes")):
            n += 1
            qs.append({"id": f"g{n:05d}", "question": text,
                       "expect": {"answerable": True, "facts": [fact], "support_docs": [f"route-r{k}.md"]}})
        # trap 1: a route number that does not exist (sibling of an existing one)
        n += 1
        qs.append({"id": f"g{n:05d}", "question": f"How often does route R{routes + k} depart from {a}?",
                   "expect": {"answerable": False}})
        # trap 2: an existing route at a stop it does not serve
        other = next(s for s in stops if s not in used[k])
        n += 1
        qs.append({"id": f"g{n:05d}", "question": f"How often does route R{k} depart from {other}?",
                   "expect": {"answerable": False}})
    rng.shuffle(qs)
    return docs, qs, truth
