# Examples

This directory contains complete, runnable examples demonstrating how to use the `ansible-role-aruba-cx-switch` role.

## Available Examples

### 2. [bgp-evpn-fabric/](bgp-evpn-fabric/)

**Best for:** Production BGP/EVPN deployments

A complete EVPN/VXLAN fabric example showing:

- Multi-tier inventory (spines, leafs, border leafs)
- BGP route reflector configuration
- EVPN/VXLAN with VRF integration
- Complete NetBox data structure
- Production-grade playbooks

**Use this to:** Deploy a full data center fabric with EVPN/VXLAN.

## Prerequisites

All examples assume you have:

1. **Ansible installed** with required collections:

    ```bash
    ansible-galaxy install -r requirements.yml
    ```

2. **NetBox access** (or sample data provided):

    - NetBox URL and API token
    - NetBox pynetbox Python library

    ```bash
    pip install -r requirements.txt
    ```

3. **Network connectivity** to your switches:

    - Management network access
    - SSH connectivity
    - Valid credentials

## Quick Start

1. Choose an example directory
2. Copy it to your working directory
3. Update the inventory with your switches
4. Configure NetBox URL and credentials
5. Review and customize group_vars
6. Run the playbook

```bash
# Example: Running minimal deployment
cd minimal-deployment
cp inventory/hosts.yml.example inventory/hosts.yml
# Edit inventory/hosts.yml with your switches
ansible-playbook -i inventory/hosts.yml playbook.yml
```

## NetBox Integration

Each example includes sample NetBox data exports showing how to structure your NetBox data. You can:

- **Use the samples** to understand required NetBox data structure
- **Import samples** into your test NetBox instance
- **Adapt your existing NetBox data** based on the examples

See [NETBOX_INTEGRATION.md](../docs/NETBOX_INTEGRATION.md) for detailed NetBox setup guidance.

## Using with Your Environment

To adapt these examples:

1. **Inventory:** Update device names and IP addresses
2. **Credentials:** Use Ansible Vault for passwords/tokens:

   ```bash
   ansible-vault create inventory/group_vars/all/vault.yml
   ```

3. **NetBox URL:** Update NetBox connection settings
4. **Variables:** Customize configuration in group_vars
5. **Tags:** Use Ansible tags to run specific configuration sections

## Documentation

For detailed documentation, see:

- **[QUICKSTART.md](../docs/QUICKSTART.md)** - Role development quick start
- **[FILTER_PLUGINS.md](../docs/FILTER_PLUGINS.md)** - Understanding NetBox data transformation
- **[BGP_CONFIGURATION.md](../docs/BGP_CONFIGURATION.md)** - BGP/EVPN setup guide
- **[NETBOX_INTEGRATION.md](../docs/NETBOX_INTEGRATION.md)** - NetBox integration details
- **[README_DOCS.md](../docs/README_DOCS.md)** - Complete documentation index

## Getting Help

If you encounter issues:

1. Check the example's README.md for specific instructions
2. Review the [documentation](../docs/)
3. Verify NetBox data structure matches the samples
4. Test with `--check` mode first
5. Use tags to isolate specific configuration sections

## Contributing Examples

Have a useful example? Contributions welcome! See [CONTRIBUTING.md](../docs/CONTRIBUTING.md) for guidelines.
