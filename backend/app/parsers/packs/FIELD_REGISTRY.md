# FIELD_REGISTRY.md
# Canonical field list — every control_area that any spec.yaml is allowed to emit.
# Rules packs must only reference names from this list.
# Last updated: 2026-09-24

## Identity

| control_area       | Description                                              |
|--------------------|----------------------------------------------------------|
| `hostname`         | Device hostname string                                   |
| `domain_name`      | DNS domain name configured on the device                 |
| `firmware_version` | Running OS/firmware version string (e.g. "15.4", "21R3")|
| `model`            | Hardware model identifier                                |
| `serial_number`    | Chassis serial number                                    |

## Management Plane

| control_area                | Description                                                    |
|-----------------------------|----------------------------------------------------------------|
| `service_password_encryption` | Cisco `service password-encryption` state (`enabled`/`disabled`) |
| `aaa_new_model`             | AAA new-model state (`enabled`/`disabled`)                     |
| `aaa_root`                  | Arista AAA root state (`enabled`/`disabled`)                   |
| `ssh_version`               | SSH protocol version configured (e.g. `2`, `v2`)              |
| `ssh_idle_timeout`          | SSH idle timeout in seconds (Arista)                           |
| `ssh_root_login`            | JunOS root-login setting (`deny`, `deny-password`, `allow`)    |
| `http_server`               | HTTP management server state (`enabled`/`disabled`)            |
| `http_secure_server`        | HTTPS management server state (`enabled`/`disabled`)           |
| `enable_secret_type`        | Cisco enable secret hash type digit (e.g. `"8"`, `"9"`)       |
| `admin_privilege`           | Arista privilege-15 username                                   |

## NTP / Time

| control_area      | Description                              |
|-------------------|------------------------------------------|
| `ntp_server`      | NTP server address (multi)               |
| `ntp_authenticate`| NTP authentication state (`enabled`/`disabled`) |
| `time_zone`       | Configured timezone                      |

## Logging / Syslog

| control_area      | Description                                         |
|-------------------|-----------------------------------------------------|
| `logging_host`    | Remote syslog server IP or hostname (multi)         |
| `logging_buffered`| Local buffer size for logging                       |
| `logging_console` | Console logging level                               |

## DNS

| control_area  | Description                  |
|---------------|------------------------------|
| `name_server` | DNS name-server address (multi) |

## SNMP

| control_area    | Description                          |
|-----------------|--------------------------------------|
| `snmp_community`| SNMP community string (multi, skip)  |
| `snmp_version`  | SNMP version configured              |

## Banner

| control_area  | Description                         |
|---------------|-------------------------------------|
| `banner_motd` | MOTD banner delimiter or first token |

## VTY / Line-scoped (instance_id = line range e.g. "vty 0 4")

| control_area    | Description                                                        |
|-----------------|--------------------------------------------------------------------|
| `transport_input`| Allowed transport protocols on VTY (`ssh`, `telnet`, `none`, etc.) |
| `exec_timeout`  | Session inactivity timeout in **total seconds** (after transform)  |
| `access_class`  | ACL applied to VTY lines                                           |
| `login_method`  | Login method configured on VTY (`local`, `tacacs`, etc.)          |

## Interface-scoped (instance_id = interface name)

| control_area          | Description                                            |
|-----------------------|--------------------------------------------------------|
| `proxy_arp`           | Interface proxy-ARP state (`enabled`/`disabled`)       |
| `ip_redirects`        | Interface IP redirects state (`enabled`/`disabled`)    |
| `ip_unreachables`     | Interface IP unreachables state (`enabled`/`disabled`) |
| `interface_description`| Interface description text                            |
| `interface_vrf`       | VRF assigned to an interface                           |
| `switchport_mode`     | Switchport mode (`access`/`trunk`)                     |

---

## Rules for adding new fields

1. Pick a name in `snake_case` that matches the config concept, not the vendor CLI token.
2. Add it to this table first, then to the appropriate spec.yaml(s).
3. If the field is vendor-specific, document which packs produce it.
4. If a transform is applied (e.g. `present_absent`, `exec_timeout_seconds`), note the output format.
