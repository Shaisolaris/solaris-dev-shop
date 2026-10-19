# G25 - Reliable device and event protocol (simulator only)

Everything here is synthetic. The devices, the lossy link and the valves are Python objects in
`employees/engineering/iot-engineer/device_protocol.py`; no hardware, serial port, radio or network is
touched, and no result below is a claim about a physical device. Every report says so in `claim_scope`.

| file | what it is |
|---|---|
| `protocol_oracle.py` | black-box oracle, 12 checks, runs any tool that speaks the CLI |
| `noop_stub.py` | claims nothing and reports clean; must fail the oracle |
| `naive_stub.py` | claims every `done` ack line (at-least-once, no sessions, no dedupe); must fail |
| `fixtures/commands.jsonl` | four synthetic commands for two valves |
| `fixtures/clean-events.jsonl` | clean control: in order, each command acked once (exit 0, 4 claims) |
| `fixtures/faulty-events.jsonl` | duplicates, local reordering, a reboot that re-sends an ack, an old-boot replay (exit 1, still 4 claims) |
| `fixtures/malformed-events.jsonl` | the clean stream with 9 malformed lines between its records (exit 1, 9 quarantined, 4 claims) |
| `fixtures/unexplained-events.jsonl` | a state change without a command, a misrouted ack and an unknown command (exit 1, 0 claims) |

## Run

    T="python3 employees/engineering/iot-engineer/device_protocol.py"
    $T ingest --commands examples/capabilities/G25/fixtures/commands.jsonl \
              --events examples/capabilities/G25/fixtures/faulty-events.jsonl
    $T simulate --devices 12 --steps 300 --seed 7 \
              --faults drop=0.2,dup=0.2,reorder=0.3,disconnect=0.05,reboot=0.02
    python3 examples/capabilities/G25/protocol_oracle.py --tool "$T"
    python3 -m unittest tests.test_g25_capability

## Oracle checks
o1 clean control; o2 duplicates, local reordering and retried acks; o3 a lost sequence number is a
gap; o4 old-boot replay and a re-sent ack after reboot; o5 misrouted, unknown, refused and wrong-state
acks; o6 malformed and over-long lines bounded; o7 unexplained transitions and fault acks; o8 three
seeds of heavy faults, claims equal ground truth and replay of the record agrees; o9 crash drill at six
points, resume equals an unbroken run, changed input refuses to resume; o10 invalid invocations exit 2
and write nothing; o11 200 devices under faults, deterministic per seed; o12 unseen generated streams.

What is not covered: real radios, timing, flash wear or power loss on real parts, record
authentication, and any physical effect. Those need bench hardware and stay out of scope.
