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
- `2001:db8:a11::1/64` - Role: `anycast`

## Generated Configuration

For the example above, the role will generate:

```
interface vlan11
    vrf attach z13-cust_2
    ip address 172.20.4.1/27
    active-gateway ip 172.20.4.1 mac 02:01:00:00:01:00
    ipv6 address 2001:db8:a11::1/64
    active-gateway ipv6 2001:db8:a11::1 mac 02:01:00:00:01:00
    ip mtu 9198
    l3-counters
```

## How It Works

### Filter Plugin Enhancement

The `get_interface_ip_addresses()` filter has been extended to:

1. Extract the IP address **role** from NetBox
2. Extract the **anycast gateway MAC** from interface custom fields
3. Include this information in the interface/IP data structure

### Task Logic

The VLAN interface configuration tasks (`configure_l3_vlan.yml`) conditionally add the `active-gateway` command:

**IPv4**:

```jinja2
{{'active-gateway ip ' + (item.address | ansible.utils.ipaddr('address')) + ' mac ' + item.anycast_mac if (item.ip_role == 'anycast' and item.anycast_mac) else []}}
```

**IPv6**:

```jinja2
{{'active-gateway ipv6 ' + (item.address | ansible.utils.ipaddr('address')) + ' mac ' + item.anycast_mac if (item.ip_role == 'anycast' and item.anycast_mac) else []}}
```

> **Note**: The `ansible.utils.ipaddr('address')` filter is used to extract only the IP address without the prefix length (e.g., `192.168.1.1` from `192.168.1.1/24`). The `active-gateway` command requires the IP address without the CIDR notation.

The `active-gateway` command is only added when:

- The IP address role is `anycast` **AND**
- The interface has an anycast MAC address defined

## Requirements

### Ansible Collections

This feature requires the `ansible.utils` collection for IP address manipulation:

```bash
ansible-galaxy collection install ansible.utils
```

The `ipaddr` filter from `ansible.utils` is used to extract the IP address without the prefix length, which is required by the AOS-CX `active-gateway` command.

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
    ip address 172.20.4.1/27
    active-gateway ip 172.20.4.1/27 mac 02:01:00:00:01:00
    ...
```

## Idempotency

The anycast gateway configuration follows the same idempotency patterns as other L3 interface configuration:

- **IPv4**: Only configured when the IP address needs to be added

## Troubleshooting

### Anycast Gateway Not Applied

**Issue**: IP address configured but no `active-gateway` command

**Possible Causes**:

1. IP address **role** is not set to `anycast` in NetBox
2. Interface **if_anycast_gateway_mac** custom field is not set or is null
3. IP address belongs to default VRF instead of custom VRF (check VRF assignment)

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
TASK [Configure VLAN interfaces (custom VRF) - IPv4] ****************************
changed: [z13-cx3] => (item=Interface: vlan11 IP: 172.20.4.1/27 Interface VRF: z13-cust_2 Role: anycast)
ok: [z13-cx3] => (item=Interface: vlan11 IP: 172.20.4.2/27 Interface VRF: z13-cust_2 Role: none)

TASK [Configure VLAN interfaces (custom VRF) - IPv6] ****************************
ok: [z13-cx3] => (item=Interface: vlan11 IP: 2001:db8:a11::1/64 Interface VRF: z13-cust_2 Role: anycast)
ok: [z13-cx3] => (item=Interface: vlan11 IP: 2001:db8:a11::2/64 Interface VRF: z13-cust_2 Role: none)
```

Notice the `Role: anycast` label in the output for anycast gateway IPs.
