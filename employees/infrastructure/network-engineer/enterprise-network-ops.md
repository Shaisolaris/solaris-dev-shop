# Enterprise Network Ops Reference

Methodology lifted from ECC (affaan-m/everything-claude-code, MIT) skills: network-config-validation, cisco-ios-patterns, netmiko-ssh-automation, network-bgp-diagnostics, network-interface-health. All snippets are illustrative patterns - confirm the platform, interface names, current config, rollback path, and out-of-band access before touching a real device. Read-only first; diagnostics before action; resets and policy changes are change-window-only.

---

## 1. Config validation (pre-deploy gate)

Treat validation as layered evidence, not a parser. Regex gives pre-flight warnings; final approval needs a human reviewing intent, platform syntax, and rollback. Validate in order:

1. Destructive commands.
2. Credential and management-plane exposure.
3. Duplicate addresses and overlapping subnets.
4. Stale references to ACLs, route-maps, prefix-lists, interfaces.
5. Operational hygiene (NTP, timestamps, remote logging, banners).

Dangerous-command patterns (fail closed): `reload` (downtime), `erase startup|nvram|flash`, `format`, `no router bgp|ospf|eigrp` (removes routing process), `no interface ...`, `aaa new-model` (changes auth behavior), `crypto key zeroize|generate` (changes SSH keys).

Duplicate IPs / subnet overlaps: extract `ip address X Y` per interface block, compute the network with the mask, flag any IP appearing twice and any pair of networks where `left.overlaps(right)`.

Management-plane (parse VTY blocks by section so checks do not spill across unrelated lines): flag `transport input ... telnet` (require SSH only), missing inbound `access-class ... in`, missing `exec-timeout N N`.

Security hygiene patterns: `snmp-server community public|private` (default community), any SNMPv2 community (prefer SNMPv3 authPriv), `ip ssh version 1`, `enable password` (use `enable secret`), `username ... password` (use secret). Best-practice presence checks: NTP server, `service timestamps`, logging destination, `snmp-server group ... v3 priv`, login/motd banner.

Use as a blocking gate before Netmiko/NAPALM/Ansible/vendor-API pushes: fail closed on dangerous commands and credentials, warn on best-practice gaps outside the change scope. Never apply generated config without a dry-run diff.

Anti-patterns: treating regex as a device parser; applying generated config without a diff; recommending SNMPv2 communities as a monitoring requirement; VTY regex that spans unrelated sections; testing firewall behavior by disabling ACLs instead of reading counters/logs.

---

## 2. Cisco IOS / IOS-XE patterns

Treat IOS examples as patterns, not paste-ready production changes. Preferred workflow:

1. Capture current state with read-only commands.
2. Review the exact candidate config.
3. Confirm management access cannot be locked out.
4. Apply the smallest change in a maintenance window.
5. Re-read state, compare to baseline, then save only after validation.

Mode reference:
```
Router> enable
Router# show running-config
Router# configure terminal
Router(config)# interface GigabitEthernet0/1
Router(config-if)# description UPLINK-TO-CORE
Router(config-if)# no shutdown
Router(config-if)# end
Router# show running-config interface GigabitEthernet0/1
```
`running-config` is active memory; `startup-config` survives reload. A command being accepted is not validation - `copy running-config startup-config` only after behavior is validated and approved.

Read-only collection menu (grab only the section you need; configs carry secrets/topology):
```
show version | show inventory | show processes cpu sorted | show memory statistics
show logging | show ip interface brief | show interfaces | show interfaces status
show vlan brief | show mac address-table | show spanning-tree | show ip route
show ip protocols | show ip access-lists | show route-map | show ip prefix-list
show running-config | section line vty|interface|router bgp
```

Wildcard masks (IOS ACLs use wildcard, NOT subnet masks):
```
255.255.255.255 -> 0.0.0.0
255.255.255.252 -> 0.0.0.3
255.255.255.0   -> 0.0.0.255
255.255.0.0     -> 0.0.255.255
```
A subnet mask used as a wildcard matches far more traffic than intended. Every ACL has an implicit deny; add an explicit logged deny only when observing misses and the log volume is safe.

ACL placement review before applying: direction (`in`/`out`?); management sourced from a known jump host/subnet?; explicit permits for routing/DNS/NTP/monitoring/app traffic?; hit counters available from a safe test source?; rollback + active console/out-of-band path?

Interface hygiene: clear descriptions, explicit `switchport mode`, documented native VLAN; on routed interfaces confirm mask, peer addressing, and routing process before assuming link state means forwarding works.

Change-window verification (match the actual change):
```
show running-config | section interface GigabitEthernet0/1
show interfaces GigabitEthernet0/1
show logging | include GigabitEthernet0/1|changed state|line protocol
show ip route <prefix>
show ip access-lists <name>
```
For routing changes capture neighbor state and route tables before/after; for ACL changes compare hit counters from a planned test source, not a generic ping.

Anti-patterns: applying generated config without a device-specific diff; saving before post-change checks pass; subnet mask where IOS wants wildcard; ACL on the wrong direction; troubleshooting by disabling ACLs/route policy/auth; pasting full configs into public tools without sanitizing.

---

## 3. Netmiko SSH automation (read-only default)

Safety defaults: start with read-only `send_command()`; explicit small inventory (no CIDR sweeps); credentials from env/vault/`getpass` (never hardcoded); set connection + read timeouts; limit concurrency; require an explicit operator flag before `send_config_set()`; do not `save_config()` until verified and approved.

Read-only connection (illustrative):
```python
device = {
  "device_type": "cisco_ios", "host": "192.0.2.10",
  "username": os.environ.get("NETMIKO_USERNAME") or input("Username: "),
  "password": os.environ.get("NETMIKO_PASSWORD") or getpass("Password: "),
  "secret": os.environ.get("NETMIKO_ENABLE_SECRET"),
  "conn_timeout": 10, "auth_timeout": 20, "banner_timeout": 15,
  "read_timeout_override": 30,
}
with ConnectHandler(**device) as conn:
    if device.get("secret") and not conn.check_enable_mode():
        conn.enable()
    output = conn.send_command("show ip interface brief", read_timeout=30)
```
Catch `NetmikoAuthenticationException`, `NetmikoTimeoutException`, `ReadTimeout`. Use documentation-range placeholders; keep real inventory in an ignored/secrets-managed file.

Batch: bounded `ThreadPoolExecutor(max_workers=8)`, return `{host, ok, output|error}` per device so one failure does not stop the batch. Keep `max_workers` low unless the estate and AAA can handle the load.

Structured parsing: `send_command(..., use_textfsm=True, raise_parsing_error=False)`. If the result is still a `str`, no template matched - store raw for review. Keep raw output alongside any parsed result that drives a blocking decision.

Guarded config:
```python
apply_changes = os.environ.get("APPLY_NETWORK_CHANGES") == "1"
if not apply_changes:
    print("Dry run only. Candidate commands:\n" + "\n".join(commands))
else:
    with ConnectHandler(**device) as conn:
        conn.enable()
        before = conn.send_command("show running-config interface Gi0/1")
        out = conn.send_config_set(commands)
        after = conn.send_command("show running-config interface Gi0/1")
        # Verify behavior BEFORE saving startup config.
```
Saving is a separate approval step with a rollback snippet and captured before/after evidence.

Review checklist: explicit inventory source?; creds absent from source/logs/exceptions?; timeouts set?; per-device failure isolation?; no broad scans / unbounded concurrency?; config behind dry-run/operator flag?; `save_config()` separate and tied to verification?

Anti-patterns: hardcoded secrets; config as the default path; automation against a CIDR range; logging full configs unsanitized; treating parser success as proof of device state.

---

## 4. BGP diagnostics (diagnostics only)

Default workflow is read-only evidence collection; policy and reset actions belong in a reviewed change window.

Read-only triage flow:
1. Identify the exact neighbor, address family (AFI/SAFI), VRF, and local/remote ASNs.
2. Capture summary state and last reset reason.
3. Prove reachability to the peer source address.
4. Check route policy references before assuming transport failure.
5. Compare advertised, received, and installed routes where supported.
```
show bgp summary | show bgp neighbors <peer> | show ip route <peer>
show tcp brief | include <peer>|:179
show logging | include BGP|<peer>
show running-config | section router bgp
show ip prefix-list | show route-map
```
Use platform-specific address-family commands for VRF/IPv6/VPNv4/EVPN; do not assume global IPv4 unicast.

State interpretation:

| State | First checks |
|---|---|
| Established + prefix count | Route exchange up; inspect policy and table selection |
| Established + 0 prefixes | Inbound policy, max-prefix, advertised routes, AFI/SAFI |
| Active | TCP not completing; routing, source, ACLs, peer reachability |
| Connect | TCP in progress; path and remote listener |
| OpenSent/OpenConfirm | TCP works; ASN, auth, timers, capabilities, logs |
| Idle | Disabled, missing config, blocked by policy, or backoff timer |

Transport checks: `ping <peer> source <local-source>`, `traceroute <peer> source <local-source>`, `show ip route <peer>`, `show bgp neighbors <peer> | include BGP state|Last reset|Local host|Foreign host`. If the peer is sourced from a loopback, confirm both directions route to the loopbacks and the config uses the expected update source.

Route policy / AS-path: `show bgp neighbors <peer> advertised-routes|routes`, `show ip prefix-list <name>`, `show route-map <name>`, `show bgp <prefix>`. AS-path regex needs token boundaries (`_65001_` matches AS 65001 as a token; bare `65001` can match longer ASNs). Some platforms need extra config before `received-routes` is available - do not add it during incident triage without approval.

A simple BGP-summary parser can classify each row as Established (numeric prefix count) vs a state string, but store raw output with the incident record because formats vary by platform and address family.

Change-window only (never auto-suggested as diagnostics): clearing a session; changing neighbor auth/timers/update-source/route-maps/prefix-lists; enabling extra received-route storage; relaxing firewall/ACL/control-plane policy. If a reset is approved, prefer the least disruptive soft/route-refresh option and document why it is safe.

Anti-patterns: assuming `Active` means the remote side is down; ignoring VRF/AFI/update-source differences; broad AS-path regex without boundaries; hard-resetting before reading last reset reason and logs; treating missing `received-routes` output as proof no routes arrived.

---

## 5. Interface health

Counters are evidence, but trend matters more than the absolute number. Capture a baseline, wait a measurement interval, capture again, compare increments.
```
show interfaces <interface>
show interfaces <interface> status
show logging | include <interface>|changed state|line protocol
# Linux: ip -s link show <if> | ethtool <if> | ethtool -S <if>
```

Counter reference:

| Counter | Meaning | Common cause |
|---|---|---|
| CRC | RX frame checksum failed | Bad cable, dirty fiber, bad optic, duplex mismatch |
| input errors | Aggregate RX errors | Check sub-counters before concluding |
| runts | Below min Ethernet size | Duplex mismatch, collision domain, faulty NIC |
| giants | Larger than expected MTU | MTU mismatch / jumbo boundary |
| input drops | Device could not accept inbound | Burst, oversubscription, CPU path, queue pressure |
| output drops | Egress queue discarded | Congestion, QoS policy, undersized uplink |
| resets | Interface hardware reset | Flapping, keepalive, driver, optic, power |
| collisions | Ethernet collisions | Half duplex / negotiation mismatch |

Diagnosis flow:
- CRCs / input errors: confirm counters are incrementing (not historical); check BOTH ends of the link (RX errors point to the signal arriving on that side); replace patch cable or clean/replace fiber+optics; confirm speed/duplex match; check logs for flaps at the same timestamp.
- Drops: separate input from output drops; compare rate vs capacity; check QoS/queue counters and oversubscribed uplinks; treat queue tuning as secondary - first prove congestion.
- Duplex/speed: prefer auto-negotiation when both sides support it; if one side is fixed, configure both sides explicitly and document why; never mix fixed on one side with auto on the other.

A safe parser slices each interface block from one header to the next (not an arbitrary character window, which can misattribute counters).

Worked examples:
- CRCs on one switch port: capture local + remote counters; replace cable/optic before changing routing or firewall; clear counters only after recording the baseline; recheck after a fixed interval.
- "Internet slow, LAN fine": check WAN drops/errors; check LAN uplink utilization and output drops; check gateway CPU if the WAN link is clean but throughput is low; compare wired vs wireless before blaming upstream.

Anti-patterns: clearing counters before saving a baseline; looking at only one side of a link; assuming all historical CRCs are active without a time window; mixing auto and fixed duplex; treating output drops as a cable problem before checking congestion.
