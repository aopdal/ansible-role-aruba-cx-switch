# Examples

This page walks through documented examples showing how to use the `ansible-role-aruba-cx-switch` role. Each example has a narrative guide here plus a runnable project under the repository's [`examples/`](../examples/) directory — you can copy that directory as a starting point, or just read the narrative guide and adapt the snippets into your own project structure.

## Available Examples

### [BGP EVPN Fabric](examples/bgp-evpn-fabric.md)

**Runnable project:** [`examples/bgp-evpn-fabric/`](../examples/bgp-evpn-fabric/)

**Best for:** Production BGP/EVPN deployments

A complete EVPN/VXLAN fabric walkthrough showing:

- Multi-tier inventory (spines, leafs, border leafs)
- BGP route reflector configuration
- EVPN/VXLAN with VRF integration
- Complete NetBox data structure
- Production-grade playbooks

**Use this to:** Deploy a full data center fabric with EVPN/VXLAN.

### OSPF Authentication

**Runnable project:** [`examples/ospf-authentication/`](../examples/ospf-authentication/)

**Best for:** Adding per-VRF OSPF MD5 authentication to existing deployments

Shows the recommended var layout for supplying per-VRF OSPF MD5 keys to the role: an encrypted `vault.yml` holding the keys, plus a plaintext indirection layer the role consumes. Covers the cleartext-then-ciphertext workflow for rotating keys without breaking idempotency.

**Use this to:** Add OSPF authentication to your inventory's `group_vars`.

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

1. Read through the [BGP EVPN Fabric](examples/bgp-evpn-fabric.md) guide
2. Copy `examples/bgp-evpn-fabric/` into your own working directory (or work from it directly)
3. Update the inventory with your switches
4. Configure NetBox URL and credentials
5. Review and customize group_vars
6. Run the playbook

```bash
cd examples/bgp-evpn-fabric
pip install -r requirements.txt
ansible-galaxy install -r requirements.yml
# Edit netbox_inventory.yml / group_vars with your NetBox URL and switches
ansible-playbook playbook.yml
```

## NetBox Integration

The example includes sample NetBox data showing how to structure your NetBox data. You can:

- **Use the samples** to understand required NetBox data structure
- **Import samples** into your test NetBox instance
- **Adapt your existing NetBox data** based on the examples

See [NETBOX_INTEGRATION.md](NETBOX_INTEGRATION.md) for detailed NetBox setup guidance.

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

- **[QUICKSTART.md](QUICKSTART.md)** - Role development quick start
- **[FILTER_PLUGINS.md](FILTER_PLUGINS.md)** - Understanding NetBox data transformation
- **[BGP_CONFIGURATION.md](BGP_CONFIGURATION.md)** - BGP/EVPN setup guide
- **[NETBOX_INTEGRATION.md](NETBOX_INTEGRATION.md)** - NetBox integration details

## Getting Help

If you encounter issues:

1. Review the [documentation](index.md)
2. Verify NetBox data structure matches the samples
3. Test with `--check` mode first
4. Use tags to isolate specific configuration sections

## Contributing Examples

Have a useful example? Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.
