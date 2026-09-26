# Homelab and Network Ops Reference

Methodology lifted from ECC (affaan-m/everything-the coding agent-code, MIT) skills: homelab-network-setup, homelab-vlan-segmentation, homelab-wireguard-vpn, homelab-pihole-dns, homelab-network-readiness, uncloud. All command snippets are illustrative patterns - confirm the platform, current topology, console access, and rollback before applying anything. Read-only first, change in a window.

---

## 1. Network setup (topology + IP plan)

Separate device roles before choosing gear:

```
Internet -> Modem/ONT -> Gateway (NAT, firewall, DHCP, DNS, inter-VLAN routing)
  -> Managed switch (wired clients, AP uplinks, VLAN trunks)
    -> Access points (Wi-Fi, ideally wired backhaul)
    -> Servers/NAS (stable addresses, DNS names, monitoring)
    -> Clients/IoT (DHCP pools, isolated via VLAN)
```

Gateway selection by operator fit:

| Option | Best fit | Notes |
|---|---|---|
| ISP router | Basic internet | Limited control, poor VLAN support |
| UniFi gateway | Managed home | Good UI, ecosystem lock-in |
| OPNsense / pfSense | Flexible homelab | Strong VLAN/firewall/VPN/DNS control |
| MikroTik | Advanced users | Powerful, easy to misconfigure |
| Linux router | Tinkerers | Document rollback before using as primary |

IP plan (avoid `192.168.1.0/24` when VPN is planned):

```
192.168.10.0/24  trusted clients
192.168.20.0/24  IoT / media
192.168.30.0/24  servers / NAS
192.168.40.0/24  guest Wi-Fi
192.168.99.0/24  network management

.1 gateway | .2-.49 infra reservations | .50-.240 DHCP pool | .241-.254 spare
```

Local names with `home.arpa` (reserved for home networks; avoids leakage/conflict):
`nas.home.arpa`, `pihole.home.arpa`, `gateway.home.arpa`, `switch-01.home.arpa`.

DHCP/DNS: reserve anything you SSH into, monitor, bookmark, or expose. Hand out the gateway as DNS until a local resolver is intentionally deployed, then point DHCP DNS at the resolver's reserved address. Keep a static range per subnet so replacements do not collide with dynamic leases.

Cabling/Wi-Fi: wired AP backhaul over mesh; PoE switch for APs/cameras; label both cable ends + keep a port map; gateway/switch/DNS/NAS on UPS if outages are common.

Anti-patterns: undocumented double-NAT; `192.168.1.0/24` with VPN; dynamic addresses for NAS/Pi-hole/Home Assistant; consumer routers as APs with DHCP still enabled; flat networks mixing cameras, smart plugs, laptops, and servers.

---

## 2. VLAN segmentation (the highest-impact security upgrade)

VLAN design template:

```
VLAN  Name        Subnet            Gateway        Purpose
10    trusted     192.168.10.0/24   192.168.10.1   PCs, phones, laptops
20    iot         192.168.20.0/24   192.168.20.1   Smart home devices
30    servers     192.168.30.0/24   192.168.30.1   NAS, Pi, self-hosted
40    guest       192.168.40.0/24   192.168.40.1   Visitor Wi-Fi
99    management  192.168.99.0/24   192.168.99.1   Network gear web UIs
```

For the owner's dev shop + game studio, consider extending with a Dev/Build VLAN (client code, build agents - isolated from general Trusted) and a Game-Test VLAN (console dev kits, test rigs).

SSID -> VLAN: one SSID per zone, separate passwords. Switch ports: trunk to router/APs (tagged), access to end devices (untagged). AP ports are trunks because the AP tags per-SSID traffic.

Firewall rules (all add isolation, none remove existing protections; first match wins on pfSense/OPNsense):

```
allow IoT -> Pi-hole(192.168.30.2):53        # MUST come before the RFC1918 block
block IoT -> RFC1918 (10/8, 172.16/12, 192.168/16)
allow IoT -> internet
block Guest -> local networks
allow Guest -> internet
allow Trusted -> everywhere
```

UniFi: Settings -> Networks (Purpose: Corporate, set VLAN ID + subnet + DHCP); Settings -> WiFi (map SSID to the VLAN network; enable Guest Policy for guest isolation); Traffic & Security -> Traffic Rules for block/allow.

pfSense/OPNsense: Interfaces -> Assignments -> VLANs (parent NIC + tag); assign each VLAN to an interface with the gateway IP; per-VLAN DHCP with DNS = Pi-hole IP; firewall rules top-to-bottom (allow Pi-hole:53 before RFC1918 block).

MikroTik: bridge with `vlan-filtering=yes`; bridge ports with `pvid`/`frame-types`; `/interface bridge vlan` for tagged/untagged; `/interface vlan` for gateway IPs; `/ip pool` + `/ip dhcp-server`; `/ip firewall filter` to drop IoT->Trusted.

Anti-patterns: VLANs without firewall rules (no security); Pi-hole in the IoT VLAN (Trusted can't reach it); native VLAN = management VLAN (VLAN hopping - use a dedicated unused native VLAN); same Wi-Fi password across IoT and Trusted SSIDs.

Always test isolation after each change: from IoT, ping a Trusted device - it must fail.

---

## 3. WireGuard VPN (remote access)

Model: each device has a keypair; server knows each client's public key; client knows server public key + endpoint. Encrypted UDP (default port 51820), no central CA.

Server (Linux) essentials:
- Generate keys with `umask 077` so files are private from the start; `wg genkey` -> `wg pubkey`.
- `wg0.conf` `[Interface]`: VPN subnet (e.g. `10.8.0.1/24`), `ListenPort = 51820`, `PrivateKey`.
- Scoped forwarding (NOT blanket FORWARD ACCEPT):
  ```
  PostUp iptables -A FORWARD -i wg0 -o eth0 -j ACCEPT
  PostUp iptables -A FORWARD -i eth0 -o wg0 -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
  PostUp iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
  (matching PostDown -D rules)
  ```
- `[Peer]` per client: `PublicKey` + `AllowedIPs = 10.8.0.x/32`.
- Enable `net.ipv4.ip_forward=1`; `wg-quick up wg0`; `systemctl enable wg-quick@wg0`. Replace `eth0` with the real outbound interface (`ip route show default`).

Client config:
- `[Interface]`: `PrivateKey`, `Address = 10.8.0.x/32`, optional `DNS = <pihole-ip>`.
- `[Peer]`: server `PublicKey`, `Endpoint = host.ddns.net:51820`, `AllowedIPs`, `PersistentKeepalive = 25`.

Tunnel modes:
- Split tunnel: `AllowedIPs = 192.168.x.0/24` - only home traffic via VPN (best for mobile).
- Full tunnel: `AllowedIPs = 0.0.0.0/0, ::/0` - all traffic via home (slow upload; gets home DNS/ad-block).
- Multi-subnet split (common homelab): `AllowedIPs = 192.168.10.0/24, 192.168.20.0/24, 192.168.30.0/24, 10.8.0.0/24`.

DDNS for dynamic ISP IPs (Cloudflare/DuckDNS): store credentials in a 600-mode env file, never inline, never committed. Forward only UDP 51820 to the VPN service, never to an admin UI.

Troubleshoot: `sudo wg show` (handshake age - "never"/old = not connected); is UDP 51820 open?; does the client have the correct server public key?; `cat /proc/sys/net/ipv4/ip_forward` = 1?; does `AllowedIPs` cover the target?; `dmesg | grep wireguard`; `wg-quick down wg0 && wg-quick up wg0`.

Anti-patterns: keys in version control; `0.0.0.0/0` on mobile without thinking; missing `PersistentKeepalive` on mobile; port open but `ip_forward` off; shared keypair across devices; blanket FORWARD ACCEPT.

---

## 4. Pi-hole / local DNS

Flow: device -> Pi-hole DNS -> blocked domains return null, allowed domains forwarded to upstream (Cloudflare/Google).

Install (Docker recommended):
```yaml
services:
  pihole:
    image: pihole/pihole:<pinned-release-tag>   # never 'latest' for DNS infra
    ports: ["53:53/tcp","53:53/udp","80:80/tcp"]
    environment:
      WEBPASSWORD: "${PIHOLE_WEBPASSWORD}"        # from 600-mode .env, not inline
      PIHOLE_DNS_: "1.1.1.1;1.0.0.1"
      DNSMASQ_LISTENING: "all"
    volumes: ["./etc-pihole:/etc/pihole","./etc-dnsmasq.d:/etc/dnsmasq.d"]
    restart: unless-stopped
    cap_add: [NET_ADMIN]    # only if Pi-hole serves DHCP
```
Bare-metal: assign a static IP first, then download/inspect the installer before running.

Point the network at it: router DHCP DNS -> Pi-hole IP. Keep gateway/second resolver as fallback during rollout; for strict blocking prefer a second Pi-hole over a public fallback (public fallback bypasses blocking). Test one client/VLAN before changing all scopes. Pi-hole-as-DHCP requires disabling router DHCP first (two DHCP servers conflict).

Blocklists: add adlists, run Tools -> Update Gravity (or `pihole -g` on a schedule). Whitelist false positives from the Query Log. DoH upstream: run cloudflared as a local proxy on `127.0.0.1#5053` and point Pi-hole there.

Local DNS records (use `home.arpa`, avoid `.local`): `nas.home.arpa -> 192.168.30.10`, plus CNAMEs for subdomains.

Troubleshoot: `pihole -q domain` (is it blocked, which list); `pihole -w domain` (whitelist); `pihole status`; `dig @<pihole-ip> google.com`; `pihole restartdns`; `pihole -t` (live tail).

Anti-patterns: single Pi-hole with no fallback path during setup; install without static IP; Pi-hole DHCP without disabling router DHCP; never updating gravity.

---

## 5. Network readiness (the planning front door)

This is planning/review, not copy-paste config. Required inventory before any implementation step:

| Area | Questions |
|---|---|
| Internet edge | Modem/ONT? ISP router bridged or routing? |
| Gateway | What routes, firewalls, does DHCP, terminates VPN? |
| Switching | Which ports are uplinks/access/trunks/unmanaged? |
| Wi-Fi | Which SSIDs map to which networks; APs wired or mesh? |
| Addressing | Subnets today; which ranges conflict with VPN sites? |
| DNS/DHCP | Which service hands out leases and resolver addresses? |
| Management | How will the operator reach gateway/switch/AP after changes? |
| Recovery | What can be reverted locally if DNS/DHCP/VLAN/VPN breaks? |

Trust-zone default policies: Trusted (reach shared services/management only when needed), Servers (narrow inbound from trusted), IoT (internet + explicit exceptions only), Guest (internet-only), Management (only from trusted admin devices), VPN (same or narrower than trusted).

Change sequence (small, reversible): snapshot -> reserve infra addresses -> create the new zone/VLAN without moving critical devices -> move one test client, validate DHCP/DNS/routing/internet/block behavior -> add narrow firewall exceptions -> move one low-risk group -> add VPN with the narrowest route/policy -> document final state + exceptions + rollback.

Validation evidence to collect: client gets expected DHCP lease and DNS resolver; public + `home.arpa` lookups succeed; blocked test domain blocked only where intended; gateway/DNS admin not reachable from guest/IoT.

Safety rules: keep the first answer read-only; never expose admin panels to the internet; require out-of-band/console access before changing management VLANs, trunks, firewall default policy, DHCP/DNS; keep a working path to the internet before repointing DNS/VPN routes; default-deny between zones.

---

## 6. Uncloud (self-hosted cluster bring-up)

Uncloud runs Docker services across peer machines on a WireGuard mesh. No central control plane (all machines equal); Caddy runs globally with auto-TLS from Let's Encrypt; overlay network `10.210.0.0/16`; internal DNS in the mesh. The Caddyfile is autogenerated - never edit it directly.

Machines: `uc machine init user@host --name machine-1` (bootstrap), `uc machine add user@host` (join), `uc machine ls`, `uc machine update NAME --public-ip IP`. Key init flags: `--name`, `--network 10.210.0.0/16`, `--no-caddy`, `--no-dns`, `--public-ip auto|IP|none`.

Services: `uc deploy` (from compose.yaml), `uc service run IMAGE`, `uc scale SERVICE N`, `uc service logs/exec/inspect/rm`, `uc ps`. Deploys are zero-downtime and health-gated; named volumes persist across `uc service rm`.

Port publishing:
- HTTP/HTTPS via Caddy: `-p [hostname:]container_port[/protocol]` (e.g. `-p app.example.com:8080/https`).
- TCP/UDP host-bound (bypass Caddy): `-p [host_ip:]host_port:container_port[/protocol]@host` (e.g. `-p 5432:5432@host`).

Compose extensions:
- `x-ports`: publish with domains.
- `x-caddy`: custom Caddy config per service; template funcs `{{upstreams [service] [port]}}`, `{{.Name}}`, `{{.Upstreams}}`.
- `x-machines`: placement constraints (single name or list).

Route an external (non-cluster) device through Caddy via a `pause` no-op container + a `--caddyfile` snippet:
```caddyfile
https://device.example.com {
  reverse_proxy https://192.168.1.x {
    transport http { tls_insecure_skip_verify }   # for self-signed BMC/NAS certs
  }
}
```
`uc service run --name device-bmc --caddyfile ~/device.caddyfile registry.k8s.io/pause:3.9`. Verify with `uc caddy config`. `--caddyfile` cannot combine with non-`@host` published ports. A wildcard DNS record (`*.domain -> cluster-public-ip`) means new subdomains work immediately.

Internal service DNS: `service-name`, `service-name.internal`, `rr.service-name.internal` (round-robin), `nearest.service-name.internal` (machine-local first).

Common mistakes: editing the Caddyfile directly (use `x-caddy`/`--caddyfile`); proxying a self-signed HTTPS upstream without `tls_insecure_skip_verify`; assuming anonymous volumes persist (only named ones do).
