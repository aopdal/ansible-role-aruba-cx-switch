# Testing Scripts

This directory contains helper scripts for setting up and managing the test environment.

## Scripts

### populate_netbox.py

Populates NetBox with test data for various topologies.

**Requirements:**
```bash
pip install pynetbox
```

**Usage:**
```bash
# Simple topology (1 spine, 1 leaf)
python populate_netbox.py \
  --url http://192.168.1.10:8000 \
  --token YOUR_NETBOX_TOKEN \
  --topology simple

# Full EVPN/VXLAN fabric (2 spines, 2 leafs)
python populate_netbox.py \
  --url http://192.168.1.10:8000 \
  --token YOUR_NETBOX_TOKEN \
  --topology fabric

# VSX topology (VSX pair + 2 leafs)
python populate_netbox.py \
  --url http://192.168.1.10:8000 \
  --token YOUR_NETBOX_TOKEN \
  --topology vsx
```

**What it creates:**
- Site (test-lab)
- Manufacturer (Aruba)
- Device type (CX 8360 Virtual)
- Device roles (spine, leaf, border)
- Devices with management IPs
- Interfaces (16-32 per device)
- VLANs (depends on topology)
- VRFs (depends on topology)

### validate_deployment.py

Validates that switches are configured correctly after running the role.

**Usage:**
```bash
python validate_deployment.py \
  --inventory ../inventory/hosts.yml \
  --netbox-url http://192.168.1.10:8000 \
  --netbox-token YOUR_TOKEN
```

**Checks:**
- VLANs match NetBox
- Interfaces configured correctly
- VRFs exist
- Routing protocols running (if configured)
- EVPN/VXLAN operational (if configured)

### bootstrap_switches.sh

Bootstrap script to configure initial management access on switches.

**Usage:**
```bash
# Edit script with your switch IPs and passwords
./bootstrap_switches.sh
```

**What it does:**
- Configures management IP
- Enables HTTPS REST API
- Enables SSH server
- Creates admin user
- Saves configuration

## Directory Structure

When using these scripts, organize your test environment like this:

```
~/aruba-test-environment/
├── ansible.cfg
├── inventory/
│   └── hosts.yml
├── playbooks/
│   └── test_*.yml
├── testing-scripts/          # This directory
│   ├── populate_netbox.py
│   ├── validate_deployment.py
│   └── bootstrap_switches.sh
└── logs/
    └── test-results/
```

## Getting Started

1. **Deploy NetBox**
   ```bash
   git clone https://github.com/netbox-community/netbox-docker.git
   cd netbox-docker
   docker-compose up -d
   ```

2. **Get NetBox API Token**
   - Login to NetBox (admin/admin)
   - Go to: Admin → API Tokens → Add Token
   - Copy token for use in scripts

3. **Populate NetBox**
   ```bash
   python populate_netbox.py --url http://localhost:8000 --token YOUR_TOKEN --topology simple
   ```

4. **Bootstrap Switches**
   - Connect to EVE-NG switches via console
   - Configure management IPs manually or use bootstrap script

5. **Run Ansible Role**
   ```bash
   cd ~/aruba-test-environment
   ansible-playbook -i inventory/hosts.yml playbooks/test_vlans.yml
   ```

6. **Validate Results**
   ```bash
   python validate_deployment.py --inventory inventory/hosts.yml
   ```

## See Also

- [TESTING_ENVIRONMENT.md](../docs/TESTING_ENVIRONMENT.md) - Full testing environment documentation
- [TESTING_QUICK_START.md](../docs/TESTING_QUICK_START.md) - Quick start guide
