# DNS Configuration - NetBox config_context Examples

## Complete DNS Configuration JSON Structure

Here's the JSON structure you can use in NetBox config_context for DNS configuration:

### Full Example with All Options
```json
{
  "dns_domain_name": "hpe.com",
  "dns_mgmt_nameservers": {
    "Primary": "10.10.2.10",
    "Secondary": "10.10.2.11"
  },
  "dns_name_servers": {
    "0": "4.4.4.8",
    "1": "4.4.4.10",
    "2": "8.8.8.8"
  },
  "dns_domain_list": {
    "0": "hp.com",
    "1": "aru.com",
    "2": "sea.com",
    "3": "opdal.net"
  },
  "dns_host_v4_address_mapping": {
    "host1": "5.5.44.5",
    "host2": "2.2.44.2",
    "jumphost": "10.10.1.100",
    "monitoring": "10.10.2.50"
  },
  "dns_vrf": "mgmt"
}
```

### Simple Example (Minimum Configuration)
```json
{
  "dns_domain_name": "opdal.net",
  "dns_mgmt_nameservers": {
    "Primary": "91.90.45.8",
    "Secondary": "1.1.1.1"
  }
}
```

### Management Network Example
```json
{
  "dns_domain_name": "mgmt.opdal.net",
  "dns_mgmt_nameservers": {
    "Primary": "172.20.0.8",
    "Secondary": "172.20.0.9"
  },
  "dns_name_servers": {
    "0": "172.20.0.8",
    "1": "172.20.0.9",
    "2": "8.8.8.8"
  },
  "dns_domain_list": {
    "0": "opdal.net",
    "1": "ao-test.net",
    "2": "local"
  },
  "dns_vrf": "mgmt"
}
```

### Enterprise Example with Host Mappings
```json
{
  "dns_domain_name": "company.local",
  "dns_mgmt_nameservers": {
    "Primary": "10.0.1.10",
    "Secondary": "10.0.1.11"
  },
  "dns_name_servers": {
    "0": "10.0.1.10",
    "1": "10.0.1.11",
    "2": "10.0.2.10"
  },
  "dns_domain_list": {
    "0": "company.local",
    "1": "company.com",
    "2": "internal.local"
  },
  "dns_host_v4_address_mapping": {
    "ntp1": "10.0.1.100",
    "ntp2": "10.0.1.101",
    "syslog": "10.0.1.200",
    "tacacs": "10.0.1.210",
    "netbox": "10.0.2.100",
    "ansible": "10.0.2.110"
  },
  "dns_vrf": "mgmt"
}
```

## Field Descriptions

| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `dns_domain_name` | String | No | Primary domain name | `"opdal.net"` |
| `dns_mgmt_nameservers` | Object | No | Management nameservers | `{"Primary": "10.1.1.1"}` |
| `dns_name_servers` | Object | No | DNS nameservers with numeric keys | `{"0": "8.8.8.8"}` |
| `dns_domain_list` | Object | No | Search domains with numeric keys | `{"0": "local"}` |
| `dns_host_v4_address_mapping` | Object | No | Static host-to-IP mappings | `{"host1": "1.1.1.1"}` |
| `dns_vrf` | String | No | VRF for DNS traffic | `"mgmt"` |

## Key Points

### Numeric Keys for Lists
The `dns_name_servers` and `dns_domain_list` fields use numeric keys as strings:
```json
{
  "dns_name_servers": {
    "0": "first.dns.server",
    "1": "second.dns.server",
    "2": "third.dns.server"
  }
}
```

### Management vs Regular Nameservers
- **`dns_mgmt_nameservers`**: Used for management traffic, keys can be descriptive
- **`dns_name_servers`**: Used for general DNS queries, keys must be numeric strings

### VRF Context
If not specified, DNS will use the default VRF. For management networks, typically use:
```json
{
  "dns_vrf": "mgmt"
}
```

### Host Mappings
Static host mappings create local DNS entries:
```json
{
  "dns_host_v4_address_mapping": {
    "jumphost": "10.10.1.100",
    "monitoring-server": "10.10.2.50"
  }
}
```

## Integration with Other Base Config

You can combine DNS with other base configuration in a single config_context:

```json
{
  "timezone": "europe/oslo",
  "motd": "Welcome to {{ inventory_hostname }}\\nManaged by Ansible",
  "ntp_vrf": "mgmt",
  "ntp_servers": [
    {"server": "klokke.opdal.net", "prefer": true}
  ],
  "dns_domain_name": "opdal.net",
  "dns_mgmt_nameservers": {
    "Primary": "91.90.45.8"
  },
  "dns_vrf": "mgmt"
}
```
