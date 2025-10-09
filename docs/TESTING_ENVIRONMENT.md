# Testing Environment Setup

## Overview

This document describes the comprehensive testing environment for the `ansible-role-aruba-cx-switch` role using:
- **EVE-NG**: Virtual network lab for Aruba AOS-CX switches
- **NetBox**: Source of truth for network configuration
- **Ansible**: Automation engine running the role
- **Test Framework**: Automated validation of role functionality

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Test Controller                          │
│  ┌────────────┐  ┌──────────────┐  ┌─────────────────────────┐ │
│  │  Ansible   │  │   NetBox     │  │  Test Scripts          │ │
│  │  Playbooks │──│   API        │──│  (validate configs)    │ │
│  └────────────┘  └──────────────┘  └─────────────────────────┘ │
│         │                                      │                 │
└─────────┼──────────────────────────────────────┼─────────────────┘
          │                                      │
          │ SSH/HTTPS                            │ Validation
          │                                      │
┌─────────▼──────────────────────────────────────▼─────────────────┐
│                         EVE-NG Lab                                │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │ CX Switch│────│ CX Switch│────│ CX Switch│────│ CX Switch│  │
│  │  Spine1  │    │  Spine2  │    │  Leaf1   │    │  Leaf2   │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│       │               │                │               │         │
│       └───────────────┴────────────────┴───────────────┘         │
│                    Management Network                             │
└───────────────────────────────────────────────────────────────────┘
```

## Components

### 1. EVE-NG Lab Setup

#### Topology Options

**Option A: Simple L2/L3 Testing (2 switches)**
- 1x Spine switch
- 1x Leaf switch
- Test: VLANs, LAG, basic L3, OSPF

**Option B: Full EVPN/VXLAN Fabric (4 switches)**
- 2x Spine switches (EVPN Route Reflectors)
- 2x Leaf switches (VTEP endpoints)
- Test: Full EVPN/VXLAN, BGP, VSX, redundancy

**Option C: VSX Pair Testing (4 switches)**
- 2x Spine switches (VSX pair)
- 2x Leaf switches (MCLAG clients)
- Test: VSX, MCLAG, failover scenarios

#### Virtual Switch Requirements

```yaml
# Per AOS-CX Virtual Switch
vcpu: 2
memory: 4096 MB  # 4GB recommended, minimum 2GB
disk: 16 GB
interfaces: 8-16 (depending on topology)
```

#### Management Network

```yaml
# Example management IP scheme
spine1: 192.168.1.11/24
spine2: 192.168.1.12/24
leaf1:  192.168.1.21/24
leaf2:  192.168.1.22/24

# Gateway/Controller
controller: 192.168.1.10/24
netbox:     192.168.1.10:8000  # Can be on same host
```

### 2. NetBox Setup

#### Installation Options

**Option 1: Docker Compose (Recommended for testing)**
```bash
# Quick setup using official NetBox Docker
git clone https://github.com/netbox-community/netbox-docker.git
cd netbox-docker
docker-compose up -d
```

**Option 2: Dedicated VM**
- Ubuntu 22.04 LTS
- NetBox installed via official documentation
- Persistent storage for test data

#### NetBox Configuration Structure

```yaml
# Sites
- name: "test-lab"
  slug: "test-lab"

# Device Roles
- name: "spine"
- name: "leaf"

# Device Types
- manufacturer: "Aruba"
  model: "CX 8360-32YC"  # Or your virtual switch model
  slug: "cx-8360-32yc"

# Devices
- name: "spine1"
  device_type: "cx-8360-32yc"
  device_role: "spine"
  site: "test-lab"
  primary_ip4: "192.168.1.11/24"

- name: "spine2"
  device_type: "cx-8360-32yc"
  device_role: "spine"
  site: "test-lab"
  primary_ip4: "192.168.1.12/24"

# VLANs
- vid: 10
  name: "servers"
  site: "test-lab"

- vid: 20
  name: "storage"
  site: "test-lab"

# VRFs
- name: "management"
  rd: "65000:100"

- name: "customer1"
  rd: "65000:200"

# IP Addressing
# Loopbacks, underlay, overlay IPs
```

### 3. Test Controller Setup

#### Requirements

```yaml
# Software stack
os: "Ubuntu 22.04 LTS" or "Debian 12"
python: "3.10+"
ansible: "2.15+"

# Python packages
packages:
  - ansible
  - pyaoscx  # Aruba AOS-CX Python SDK
  - pynetbox  # NetBox API client
  - pytest
  - pytest-testinfra  # Infrastructure testing
  - netmiko  # SSH connection library
  - jinja2
  - pyyaml
  - requests
```

#### Directory Structure

```
~/aruba-test-environment/
├── ansible.cfg
├── inventory/
│   ├── hosts.yml           # EVE-NG switch inventory
│   └── group_vars/
│       ├── all.yml         # NetBox connection, global vars
│       └── test_lab.yml    # Lab-specific variables
├── playbooks/
│   ├── 00_bootstrap.yml    # Initial switch setup (mgmt IP, API)
│   ├── 01_test_vlans.yml   # Test VLAN creation/deletion
│   ├── 02_test_l2.yml      # Test L2 interfaces
│   ├── 03_test_l3.yml      # Test L3 interfaces/VRFs
│   ├── 04_test_ospf.yml    # Test OSPF configuration
│   ├── 05_test_bgp.yml     # Test BGP/EVPN configuration
│   ├── 06_test_vxlan.yml   # Test VXLAN configuration
│   ├── 07_test_vsx.yml     # Test VSX configuration
│   ├── 08_test_cleanup.yml # Test idempotent cleanup
│   └── 99_reset_lab.yml    # Reset switches to baseline
├── tests/
│   ├── test_vlans.py       # pytest validation scripts
│   ├── test_interfaces.py
│   ├── test_routing.py
│   └── test_evpn.py
├── scripts/
│   ├── populate_netbox.py  # Populate NetBox with test data
│   ├── validate_config.py  # Validate switch configs
│   └── collect_logs.py     # Collect test logs
└── docs/
    ├── test_scenarios.md   # Test case documentation
    └── troubleshooting.md  # Common issues and fixes
```

## Test Scenarios

### Phase 1: Basic Connectivity & VLANs

**Test Case 1.1: Bootstrap**
- Bootstrap fresh switches with management config
- Enable REST API
- Verify SSH and HTTPS access
- Expected: All switches reachable via API

**Test Case 1.2: VLAN Creation**
- Populate NetBox with VLANs 10, 20, 30
- Run role to create VLANs
- Verify VLANs exist on switches
- Expected: All VLANs created with correct names

**Test Case 1.3: VLAN Deletion (Idempotent)**
- Remove VLAN 30 from NetBox
- Run role in idempotent mode
- Verify VLAN 30 deleted from switch
- Expected: VLAN 30 removed, VLAN 10/20 remain

**Test Case 1.4: Orphaned VLAN Cleanup**
- Manually create VLAN 99 on switch (not in NetBox)
- Run role in idempotent mode
- Expected: VLAN 99 deleted automatically

### Phase 2: L2 Interfaces

**Test Case 2.1: Access Ports**
- Configure access ports in NetBox
- Run role to apply configs
- Verify access VLAN assignments
- Expected: Ports have correct VLAN, mode access

**Test Case 2.2: Trunk Ports**
- Configure trunk ports with allowed VLANs
- Run role to apply configs
- Verify trunk mode and allowed VLANs
- Expected: Ports in trunk mode with correct VLANs

**Test Case 2.3: LAG Configuration**
- Configure LAG in NetBox
- Run role to create LAG
- Verify LAG members and LACP
- Expected: LAG active with all members

**Test Case 2.4: MCLAG (VSX)**
- Configure MCLAG between VSX pair
- Run role to configure MCLAG
- Verify MCLAG sync and status
- Expected: MCLAG operational, sync active

### Phase 3: L3 & Routing

**Test Case 3.1: VRF Creation**
- Configure VRFs in NetBox
- Run role to create VRFs
- Verify VRF existence
- Expected: VRFs created with correct RD

**Test Case 3.2: VLAN Interfaces (SVIs)**
- Configure SVIs in NetBox with IP addressing
- Run role to create SVIs
- Verify IPs and VLAN association
- Expected: SVIs up with correct IPs

**Test Case 3.3: Loopback Interfaces**
- Configure loopback IPs in NetBox
- Run role to create loopbacks
- Expected: Loopbacks configured with IPs

**Test Case 3.4: OSPF Configuration**
- Configure OSPF areas and interfaces
- Run role to configure OSPF
- Verify OSPF neighbors and routes
- Expected: OSPF adjacencies up, routes exchanged

**Test Case 3.5: BGP/EVPN Configuration**
- Configure BGP peers and EVPN address family
- Run role to configure BGP
- Verify BGP sessions and EVPN routes
- Expected: BGP sessions up, EVPN routes present

### Phase 4: Overlay & Advanced

**Test Case 4.1: VXLAN Tunnel Creation**
- Configure VXLAN VNIs in NetBox
- Run role to create VXLAN tunnels
- Verify VNI-to-VLAN mappings
- Expected: VXLAN tunnels operational

**Test Case 4.2: EVPN L2 Extension**
- Configure L2 EVPN services
- Run role to configure EVPN
- Verify MAC learning across fabric
- Expected: L2 connectivity across VXLAN

**Test Case 4.3: EVPN L3 (VRF) Services**
- Configure L3 EVPN with VRFs
- Run role to configure L3 EVPN
- Verify inter-VRF routing
- Expected: L3 connectivity with VRF isolation

**Test Case 4.4: VSX Configuration**
- Configure VSX pair parameters
- Run role to configure VSX
- Verify VSX sync and ISL
- Expected: VSX pair operational

### Phase 5: Idempotent Operations

**Test Case 5.1: No-Change Run**
- Run role twice with same config
- Verify no changes on second run
- Expected: "changed=0" on second run

**Test Case 5.2: Interface Cleanup**
- Remove interface configs from NetBox
- Run role in idempotent mode
- Verify configs removed from switch
- Expected: Interfaces reset to default

**Test Case 5.3: VLAN Cleanup After Interface Changes**
- Remove VLAN from all interfaces
- Run role in idempotent mode
- Verify VLAN deleted from switch
- Expected: VLAN removed after interface cleanup

**Test Case 5.4: VRF Deletion**
- Remove VRF from NetBox
- Run role in idempotent mode
- Verify VRF removed (after interfaces removed)
- Expected: VRF deleted cleanly

## Implementation Steps

### Step 1: EVE-NG Lab Setup (Week 1)

```bash
# 1. Import AOS-CX virtual image to EVE-NG
# 2. Create lab topology
# 3. Boot switches and configure basic management

# Example bootstrap config (via console)
configure terminal
  hostname spine1
  interface mgmt
    ip address 192.168.1.11/24
    no shutdown
  exit
  https-server vrf mgmt
  https-server rest access-mode read-write
  ssh server vrf mgmt
exit
write memory
```

### Step 2: NetBox Setup (Week 1)

```bash
# 1. Deploy NetBox using Docker
cd ~/
git clone https://github.com/netbox-community/netbox-docker.git
cd netbox-docker
docker-compose up -d

# 2. Access NetBox at http://192.168.1.10:8000
# 3. Create API token
# 4. Populate with test data using script
```

### Step 3: Test Controller Setup (Week 1)

```bash
# 1. Install requirements
sudo apt update
sudo apt install -y python3 python3-pip git

# 2. Create test environment
mkdir -p ~/aruba-test-environment
cd ~/aruba-test-environment

# 3. Install Python packages
python3 -m venv venv
source venv/bin/activate
pip install ansible pyaoscx pynetbox pytest pytest-testinfra netmiko

# 4. Install Aruba AOS-CX collection
ansible-galaxy collection install arubanetworks.aoscx

# 5. Install your role
ansible-galaxy install -f git+https://github.com/aopdal/ansible-role-aruba-cx-switch.git
```

### Step 4: Create Test Playbooks (Week 2)

```yaml
# playbooks/01_test_vlans.yml
---
- name: Test VLAN Configuration
  hosts: test_lab
  gather_facts: false
  vars:
    aoscx_configure_vlans: true
    aoscx_idempotent_mode: true
    aoscx_debug: true

  pre_tasks:
    - name: Get device ID from NetBox
      ansible.builtin.set_fact:
        device_id: "{{ lookup('netbox.netbox.nb_lookup', 'devices', api_endpoint=netbox_url, token=netbox_token, api_filter='name=' + inventory_hostname) | first | json_query('value.id') }}"

    - name: Get interfaces from NetBox
      ansible.builtin.set_fact:
        interfaces: "{{ query('netbox.netbox.nb_lookup', 'interfaces', api_endpoint=netbox_url, token=netbox_token, api_filter='device=' + inventory_hostname) }}"

  roles:
    - aopdal.aruba_cx_switch

  post_tasks:
    - name: Verify VLANs created
      arubanetworks.aoscx.aoscx_facts:
        gather_network_resources:
          - vlans
      register: result

    - name: Display VLANs
      ansible.builtin.debug:
        var: result.ansible_network_resources.vlans
```

### Step 5: Create Validation Tests (Week 2-3)

```python
# tests/test_vlans.py
import pytest
import requests
from pyaoscx.session import Session
from pyaoscx.pyaoscx_factory import PyaoscxFactory

@pytest.fixture
def switch_session():
    """Create AOS-CX API session"""
    session = Session('192.168.1.11', 'admin', 'password')
    session.open('https', 443)
    yield session
    session.close()

def test_vlan_10_exists(switch_session):
    """Test that VLAN 10 exists with correct name"""
    vlan = PyaoscxFactory.get_vlan(switch_session, 10)
    assert vlan is not None
    assert vlan.name == "servers"

def test_vlan_99_deleted(switch_session):
    """Test that orphaned VLAN 99 was deleted"""
    vlan = PyaoscxFactory.get_vlan(switch_session, 99)
    assert vlan is None

def test_idempotency(switch_session):
    """Test that running role twice makes no changes"""
    # This would be a more complex test using Ansible API
    pass
```

### Step 6: Automation & CI/CD (Week 3-4)

```yaml
# .github/workflows/integration-test.yml
name: Integration Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]
  schedule:
    - cron: '0 2 * * *'  # Nightly tests

jobs:
  integration-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Run integration tests
        run: |
          # SSH into test controller
          # Run test playbooks
          # Collect results

      - name: Publish test results
        uses: EnricoMi/publish-unit-test-result-action@v2
        with:
          files: test-results/**/*.xml
```

## Test Execution

### Manual Test Run

```bash
# 1. Activate environment
cd ~/aruba-test-environment
source venv/bin/activate

# 2. Run specific test
ansible-playbook -i inventory/hosts.yml playbooks/01_test_vlans.yml -vv

# 3. Run validation
pytest tests/test_vlans.py -v

# 4. Run full test suite
./run_all_tests.sh
```

### Automated Test Run

```bash
# Create test runner script
cat > run_all_tests.sh << 'EOF'
#!/bin/bash
set -e

echo "Starting integration test suite..."

# Run each test phase
for playbook in playbooks/0*.yml; do
    echo "Running $playbook..."
    ansible-playbook -i inventory/hosts.yml "$playbook" || exit 1
done

# Run pytest validation
echo "Running validation tests..."
pytest tests/ -v --html=report.html

echo "All tests completed successfully!"
EOF

chmod +x run_all_tests.sh
```

## Monitoring & Validation

### Real-time Monitoring

```python
# scripts/monitor_test.py
"""Monitor switch status during tests"""
import time
from pyaoscx.session import Session

def monitor_switch(ip, interval=5):
    session = Session(ip, 'admin', 'password')
    session.open('https', 443)

    while True:
        # Check system status
        # Check interface states
        # Check protocol status
        # Log to file
        time.sleep(interval)
```

### Log Collection

```bash
# scripts/collect_logs.sh
#!/bin/bash
# Collect logs from all switches

SWITCHES="spine1 spine2 leaf1 leaf2"
LOG_DIR="logs/$(date +%Y%m%d_%H%M%S)"

mkdir -p "$LOG_DIR"

for switch in $SWITCHES; do
    echo "Collecting logs from $switch..."
    ssh admin@$switch "show running-config" > "$LOG_DIR/$switch-running.cfg"
    ssh admin@$switch "show tech all" > "$LOG_DIR/$switch-tech.txt"
done
```

## Benefits of This Approach

### 1. **Realistic Testing**
- Real AOS-CX switches (virtual but authentic)
- Actual NetBox integration
- Production-like workflows

### 2. **Comprehensive Coverage**
- L2, L3, overlay, routing protocols
- Idempotent operations
- Error handling and recovery

### 3. **Repeatable**
- Automated test execution
- Consistent environment
- Version-controlled test cases

### 4. **Documentation**
- Test scenarios = role documentation
- Example playbooks for users
- Troubleshooting guides

### 5. **Continuous Validation**
- Catch regressions early
- Validate new features
- Ensure NetBox compatibility

## Cost & Resource Requirements

### Option 1: Single Server (Minimum)
```yaml
Hardware:
  CPU: 8+ cores
  RAM: 32 GB
  Disk: 200 GB SSD

Software:
  EVE-NG: Community Edition (free)
  NetBox: Docker (free)
  Ansible: Open source (free)

Total Cost: ~$0 (using existing hardware)
```

### Option 2: Dedicated Lab (Recommended)
```yaml
Hardware:
  CPU: 16+ cores
  RAM: 64 GB
  Disk: 500 GB NVMe

Software: Same as Option 1

Total Cost: ~$1000-2000 one-time (if buying hardware)
```

### Option 3: Cloud-based (Flexible)
```yaml
Provider: AWS/Azure/GCP
Instance: t3.2xlarge or equivalent
Cost: ~$200-300/month (only when testing)
```

## Timeline

### Week 1: Infrastructure Setup
- [ ] EVE-NG lab creation
- [ ] NetBox deployment
- [ ] Test controller setup
- [ ] Network connectivity verification

### Week 2: Basic Tests
- [ ] Bootstrap playbooks
- [ ] VLAN tests
- [ ] L2 interface tests
- [ ] Initial validation scripts

### Week 3: Advanced Tests
- [ ] L3/VRF tests
- [ ] Routing protocol tests
- [ ] EVPN/VXLAN tests (if applicable)
- [ ] VSX tests (if applicable)

### Week 4: Automation & Documentation
- [ ] Test automation scripts
- [ ] CI/CD integration (optional)
- [ ] Documentation
- [ ] Troubleshooting guides

## Next Steps

1. **Decision Point**: Choose topology (Simple, Full Fabric, or VSX)
2. **Resource Allocation**: Identify hardware/VM for lab
3. **Priority Testing**: Which features to test first?
4. **Timeline**: When to start implementation?

Would you like me to:
1. Create detailed NetBox population scripts?
2. Generate example test playbooks for specific scenarios?
3. Create the test validation (pytest) framework?
4. Design a specific topology based on your use case?
