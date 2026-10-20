#!/usr/bin/env python3
"""Write the shipped G22 demo stream: signed envelopes (one per line) from a readable event list.

    make_stream.py SECRET_FILE OUT.jsonl
Signs with the local test secret at fixed timestamps (T0 = 1790000000, 2026-09-21 UTC) so the stream is
reproducible; ingest it with --now 1790000200. It holds a replay, a forged signature, a stale event,
an out-of-order refund and capture, a partial refund with restock and an over-refund.
"""
import hashlib
import hmac
import json
import sys

T0 = 1790000000
EVENTS = [
    ("evt_001", "order.placed", 0, {"order_id": "ord_1", "currency": "USD", "lines": [{"sku": "mug-blue", "qty": 2}, {"sku": "tee-m", "qty": 1}]}),
    ("evt_002", "payment.captured", 60, {"order_id": "ord_1", "payment_id": "pay_1", "amount": "44.99"}),
    ("evt_002", "payment.captured", 60, {"order_id": "ord_1", "payment_id": "pay_1", "amount": "44.99"}),
    ("evt_004", "refund.succeeded", 200, {"order_id": "ord_2", "refund_id": "re_2", "amount": "0.10", "restock": [{"sku": "poster", "qty": 1}]}),
    ("evt_003", "payment.captured", 120, {"order_id": "ord_2", "payment_id": "pay_2", "amount": "0.30"}),
    ("evt_005", "order.placed", 100, {"order_id": "ord_2", "currency": "USD", "lines": [{"sku": "poster", "qty": 3}]}),
    ("evt_006", "refund.succeeded", 300, {"order_id": "ord_1", "refund_id": "re_1", "amount": "12.50", "restock": [{"sku": "mug-blue", "qty": 1}]}),
    ("evt_007", "refund.succeeded", 310, {"order_id": "ord_1", "refund_id": "re_1b", "amount": "40.00", "restock": []}),
    ("evt_008", "order.placed", 320, {"order_id": "ord_3", "currency": "USD", "lines": [{"sku": "tee-m", "qty": 5}]}),
    ("evt_009", "order.placed", 330, {"order_id": "ord_4", "currency": "USD", "lines": [{"sku": "tee-m", "qty": 3}]}),
    ("evt_010", "order.cancelled", 340, {"order_id": "ord_4"}),
]


def env(secret, eid, typ, dt, data, t=None, forge=False):
    body = json.dumps({"id": eid, "type": typ, "created": T0 + dt, "data": data}, sort_keys=True, separators=(",", ":"))
    t = T0 + dt if t is None else t
    sig = hmac.new(secret, ("%d." % t).encode() + body.encode(), hashlib.sha256).hexdigest()
    if forge:
        sig = sig[:-1] + ("0" if sig[-1] != "0" else "1")
    return json.dumps({"signature": "t=%d,v1=%s" % (t, sig), "body": body})


if __name__ == "__main__":
    secret = open(sys.argv[1]).read().strip().encode()
    lines = [env(secret, *e) for e in EVENTS]
    lines.insert(3, env(secret, "evt_099", "refund.succeeded", 90, {"order_id": "ord_1", "refund_id": "re_x", "amount": "44.99", "restock": []}, forge=True))
    lines.insert(4, env(secret, "evt_098", "payment.captured", 95, {"order_id": "ord_1", "payment_id": "pay_x", "amount": "44.99"}, t=T0 - 3600))
    open(sys.argv[2], "w").write("\n".join(lines) + "\n")
