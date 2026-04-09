# Anycast Gateway Configuration

## Overview

This document describes how to configure anycast gateway (active-gateway) on SVI interfaces using NetBox as the source of truth.

## NetBox Configuration

### IP Address Role

To mark an IP address as an anycast gateway address:

1. Navigate to the IP address in NetBox
2. Set the **Role** field to `anycast`
3. Save the IP address

### Interface Custom Field

Each interface that will have anycast gateway IPs needs the MAC address configured:

1. Navigate to the interface in NetBox
2. Set the custom field **if_anycast_gateway_mac** to the desired MAC address
   - Example: `02:01:00:00:01:00`
3. Save the interface

### Example Configuration

**Interface**: `vlan11`
**Custom Fields**:

- `if_anycast_gateway_mac`: `02:01:00:00:01:00`

**IP Addresses**:

- `172.20.4.1/27` - Role: `anycast`
- `fe80::1/64` - Role: `anycast` *(link-local — HPE Aruba recommended)*

## HPE Aruba Recommendation: Link-Local IPv6 Anycast

HPE Aruba recommends using a link-local address (`fe80::`) as the IPv6 anycast gateway rather than a global-unicast address. Link-local addresses are not routable beyond the local segment, which is the correct scope for a gateway address shared across VSX peers.

When the IPv6 anycast address is link-local, AOS-CX requires `ipv6 address link-local` to be explicitly configured **before** the `active-gateway ipv6` command:

```
interface vlan11
    ipv6 address link-local fe80::1/64
    active-gateway ipv6 mac 02:01:00:00:01:00
    active-gateway ipv6 fe80::1
```

The role handles this automatically — see [Generated Configuration](#generated-configuration) below.

## Generated Configuration

For the example above, the role will generate:

```
interface vlan11
    vrf attach z13-cust_2
    ip address 172.20.4.2/27
    active-gateway ip mac 02:01:00:00:01:00
    active-gateway ip 172.20.4.1
    ipv6 address link-local fe80::1/64
    active-gateway ipv6 mac 02:01:00:00:01:00
    active-gateway ipv6 fe80::1
    ip mtu 9198
    l3-counters
```

The `ipv6 address link-local fe80::1/64` line is emitted automatically by `build_l3_config_lines` whenever the anycast IPv6 address is a link-local address (`fe80::`). Global-unicast anycast addresses do not get this extra line.

## How It Works

### Filter Plugin Enhancement

The `get_interface_ip_addresses()` filter has been extended to:

1. Extract the IP address **role** from NetBox
2. Extract the **anycast gateway MAC** from interface custom fields
3. Include this information in the interface/IP data structure

### Task Logic

The `build_l3_config_lines()` filter (`filter_plugins/netbox_filters_lib/l3_config_helpers.py`) generates all CLI configuration lines for an interface in a single call, including the `active-gateway` commands. It emits lines in the order AOS-CX requires:

1. VRF attachment (once)
2. Regular IPv4 addresses (`ip address`)
3. Anycast IPv4 — MAC command first, then IP without prefix:
   ```
   active-gateway ip mac <mac>
   active-gateway ip <ip-without-prefix>
   ```
4. Regular IPv6 addresses (`ipv6 address`)
5. Anycast IPv6 — link-local address if needed, then MAC, then IP without prefix:
   ```
   ipv6 address link-local <fe80-address-with-prefix>  # only for link-local anycast
   active-gateway ipv6 mac <mac>
   active-gateway ipv6 <ip-without-prefix>
   ```
6. MTU, L3 counters, OSPF (once)

The prefix is stripped in Python (`address.split("/")[0]`) — no Ansible collection is needed for this.

The `active-gateway` commands are only emitted when:

- The IP address role is `anycast` **AND**
- The interface has an anycast MAC address defined (`if_anycast_gateway_mac` custom field)

## Requirements

### NetBox Setup

1. IP address **role** field must support `anycast` value
   - This may require custom choice configuration in NetBox
2. Interface custom field `if_anycast_gateway_mac` must exist
   - Type: Text
   - Content Type: dcim > interface

### VSX Configuration

Anycast gateway is typically used in VSX (Virtual Switching Extension) configurations where both switches in the pair use the same anycast MAC:

```yaml
# Example VSX local context data
vsx_system_mac: "02:01:00:00:01:00"
```

## Validation

### Check NetBox Data

```bash
# Verify IP addresses with anycast role
ansible-playbook your-playbook.yml -i inventory.yml --tags debug -e "aoscx_debug=true"
```

Look for debug output showing:

```
Matched IP 172.20.4.1/27 to interface vlan11 (VRF: z13-cust_2, Role: anycast, Anycast MAC: 02:01:00:00:01:00)
```

### Check Device Configuration

```
show running-config interface vlan11
```

Should show:

```
interface vlan11
    ...
    ip address 172.20.4.2/27
    active-gateway ip mac 02:01:00:00:01:00
    active-gateway ip 172.20.4.1
    ipv6 address link-local fe80::1/64
    active-gateway ipv6 mac 02:01:00:00:01:00
    active-gateway ipv6 fe80::1
    ...
```

Note that the `active-gateway ip mac` line appears before `active-gateway ip` (AOS-CX requires this order), and the IP in the `active-gateway ip` command has no CIDR prefix.

## Idempotency

The anycast gateway configuration follows the same idempotency patterns as other L3 interface configuration:

- **IPv4**: Only configured when the IP address needs to be added (compares against `vsx_virtual_ip4`)
- **IPv6**: Only configured when the address is absent from `vsx_virtual_ip6`
- **`ipv6 address link-local`**: Detected via the `ip6_address_link_local` REST API field (requires `aoscx_gather_facts_rest_api: true`). The role compares the device's currently active link-local address against the expected link-local anycast. If it does not match (e.g., only the auto-generated EUI-64 address is active), the interface is marked with `_ip_changes.link_local_ipv6_to_add` and the command is applied in a dedicated task before the main L3 config runs.

## Troubleshooting

### Anycast Gateway Not Applied

**Issue**: IP address configured but no `active-gateway` command

**Possible Causes**:

1. IP address **role** is not set to `anycast` in NetBox
2. Interface **if_anycast_gateway_mac** custom field is not set or is null
3. IP address belongs to default VRF instead of custom VRF (check VRF assignment)

### `ipv6 address link-local` Not Applied

**Issue**: Interface has `active-gateway ipv6 fe80::1` but the `ipv6 address link-local fe80::1/64` command is missing (e.g., after migrating from a global-unicast anycast to a link-local anycast).

**Cause**: The role detects this via `ip6_address_link_local` in the REST API facts. If `aoscx_gather_facts_rest_api: false`, the detection is skipped and the command will not be applied.

**Solution**: Enable `aoscx_gather_facts_rest_api: true` and re-run the playbook. The role will detect the mismatch (device's active link-local is the auto-generated EUI-64 address, not `fe80::1`) and apply `ipv6 address link-local fe80::1/64` automatically.

**Debug**:

```bash
export DEBUG_ANSIBLE=true
ansible-playbook your-playbook.yml -i inventory.yml --limit your-switch
```

Look for the filter debug output showing IP role and anycast MAC values.

### Wrong MAC Address

**Issue**: Active-gateway configured with incorrect MAC

**Solution**: Update the `if_anycast_gateway_mac` custom field on the interface in NetBox and re-run the playbook.

### Multiple VLANs with Same Anycast IP

This is valid for anycast gateway - multiple VLANs can use the same IP address in different VRFs:

- `vlan11` in VRF `customer-a`: `10.0.1.1/24` (anycast MAC: `02:01:00:00:01:00`)
- `vlan12` in VRF `customer-b`: `10.0.1.1/24` (anycast MAC: `02:01:00:00:01:00`)

Each VLAN should have the same anycast MAC configured on its interface custom field.

## Related Documentation

- [FILTER_PLUGINS.md](FILTER_PLUGINS.md) - Filter plugin documentation
- [L3 Interface Configuration](FILTER_PLUGINS.md#l3-interface-ip-address-idempotency) - IPv4/IPv6 idempotency
- AOS-CX Documentation: Anycast Gateway / Active Gateway
- VSX Configuration Guide

## Example Playbook Output

```
TASK [Configure vlan L3 interfaces (custom VRF)] ****************************
changed: [z13-cx3] => (item=Interface: vlan11)
ok: [z13-cx3] => (item=Interface: vlan11)
```

Both IPv4 and IPv6 (including `active-gateway` commands) are pushed in a single task call per interface via `build_l3_config_lines`. The loop label shows the interface name; use `DEBUG_ANSIBLE=true` or `-v` to see the generated config lines.
