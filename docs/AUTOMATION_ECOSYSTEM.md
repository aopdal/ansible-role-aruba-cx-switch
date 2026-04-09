# Network Automation Ecosystem - The Big Picture

This document provides a comprehensive overview of the network automation ecosystem where the `aopdal.aruba_cx_switch` Ansible role operates. It describes the complete lifecycle from initial device deployment through ongoing configuration management.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Components and Responsibilities](#components-and-responsibilities)
- [Lifecycle Phases](#lifecycle-phases)
- [Data Flow](#data-flow)
- [Integration Points](#integration-points)
- [Best Practices](#best-practices)

---

## Architecture Overview

```mermaid
graph TB
    subgraph NetBox["🎯 NetBox - Source of Truth"]
        direction LR
        NB1["Physical Assets<br/>• Devices<br/>• Cables<br/>• Ports<br/>• Power"]
        NB2["Logical Networks<br/>• Sites<br/>• Racks<br/>• VLANs<br/>• VRFs"]
        NB3["IP Management<br/>• Prefixes<br/>• IPs<br/>• VRFs"]
        NB4["Config Context<br/>• BGP AS<br/>• VLANs<br/>• NTP<br/>• DNS"]
        NB5["Automation<br/>• Tags<br/>• Custom Fields<br/>• Feature Flags"]
    end

    subgraph Ansible["⚙️ Automation Layer - Ansible"]
        Role["aopdal.aruba_cx_switch Role<br/><br/>Responsibilities:<br/>• Query NetBox API<br/>• Apply full configurations<br/>• Maintain idempotent state<br/>• Handle EVPN/VXLAN, BGP, OSPF, VSX"]
    end

    subgraph Deploy["📦 Deployment Paths"]
        direction LR
        ZTP["Initial Deployment<br/>ZTP Infrastructure<br/><br/>• DHCP Server<br/>  - IP Assignment<br/>  - Option 66/67<br/>  - ZTP script URL<br/><br/>• TFTP/HTTP Server<br/>  - ZTP scripts<br/>  - Base configs<br/>  - Firmware (opt)"]
        Direct["Ongoing Management<br/>Direct Connection<br/><br/>• SSH/HTTPS<br/>  - Config push<br/>  - Verification<br/>  - Monitoring"]
    end

    subgraph Switches["🔌 Network Devices"]
        SW["Aruba CX Switches<br/><br/>Phase 1: ZTP Boot<br/>Phase 2: Base Config<br/>Phase 3: Full Config"]
    end

    NetBox --> Ansible
    Ansible --> Deploy
    ZTP --> SW
    Direct --> SW

    style NetBox fill:#e1f5ff,stroke:#3f51b5,stroke-width:3px
    style Ansible fill:#fff4e1,stroke:#ff9800,stroke-width:3px
    style Deploy fill:#e8f5e9,stroke:#4caf50,stroke-width:3px
    style Switches fill:#f3e5f5,stroke:#9c27b0,stroke-width:3px
    style NB1 fill:#e3f2fd,stroke:#2196f3,stroke-width:1px
    style NB2 fill:#e3f2fd,stroke:#2196f3,stroke-width:1px
    style NB3 fill:#e3f2fd,stroke:#2196f3,stroke-width:1px
    style NB4 fill:#e3f2fd,stroke:#2196f3,stroke-width:1px
    style NB5 fill:#e3f2fd,stroke:#2196f3,stroke-width:1px
    style Role fill:#fff9c4,stroke:#fbc02d,stroke-width:2px
    style ZTP fill:#f1f8e9,stroke:#8bc34a,stroke-width:2px
    style Direct fill:#f1f8e9,stroke:#8bc34a,stroke-width:2px
    style SW fill:#f3e5f5,stroke:#ab47bc,stroke-width:2px
```

---

## Components and Responsibilities

### 1. NetBox (Source of Truth)

**Scope: Complete Network Inventory and Configuration Data**

#### In Scope (Used by This Role)

- ✅ **Device Information**: Hostname, platform, serial number, management IP
- ✅ **Interfaces**: Physical ports, LAGs, SVIs, loopbacks
- ✅ **L2 Configuration**: VLANs, trunk/access ports, allowed VLANs
- ✅ **L3 Configuration**: IP addresses, VRFs, routing
- ✅ **Routing Protocols**: BGP (via netbox-bgp plugin), OSPF areas
- ✅ **EVPN/VXLAN**: VNI mappings, EVPN instance configuration
- ✅ **Virtual Chassis**: VSX configuration data
- ✅ **Config Context**: System settings (NTP, DNS, timezone, banner)
- ✅ **Custom Fields**: Feature flags (device_bgp, device_evpn, device_vxlan, device_vsx)
- ✅ **Tags**: Automation control (ztp_ready, production, staging)

#### Out of Scope (Not Used by This Role, but Important)

- 📋 **Physical Documentation**: Cable management, rack elevations, power circuits
- 📋 **Site Information**: Address, contact information, facility details
- 📋 **Circuit Management**: WAN links, ISP information
- 📋 **Asset Management**: Purchase orders, warranties, contracts
- 📋 **Power Management**: PDUs, power feeds, redundancy

**Why Document These?**
While not used for configuration automation, these provide critical context for:

- Troubleshooting physical layer issues
- Planning upgrades and expansions
- Capacity management
- Disaster recovery

### 2. Ansible

**Scope: Configuration Orchestration and Deployment**

#### This Role (`aopdal.aruba_cx_switch`)

**Responsibilities:**

- ✅ Query NetBox API for device configuration
- ✅ Deploy complete switch configurations via SSH/HTTPS
- ✅ Maintain idempotent configuration state
- ✅ Handle complex features (EVPN, VXLAN, BGP, OSPF, VSX)
- ✅ Provide cleanup of removed configurations (idempotent mode)

**Does NOT Handle:**

- ❌ DHCP server configuration
- ❌ TFTP/HTTP server configuration
- ❌ Generate config for ZTP
- ❌ ZTP script deployment to servers
- ❌ Firmware management
- ❌ Backup/restore operations (separate roles recommended)

### 3. ZTP Infrastructure (Initial Deployment)

**Scope: Zero Touch Provisioning for New Devices**

#### DHCP Server (Out of Scope for This Role)

**Responsibilities:**

- Provide IP address to new switches
- Provide default gateway
- Provide DNS servers
- Provide ZTP bootfile-name
- Provide firmware version and location

**Example Configuration (ISC DHCP):**
```conf
# Aruba CX ZTP Configuration
subclass "Vendor-Class" "Aruba JL725A 6200F" {
    option vendor-class-identifier "Aruba JL725A 6200F";
    option aruba.image-file-name "ArubaOS-CX_6200_10_13_1040.swi";
    option aruba.config-file-name "aoscx_base.conf";
}

subclass "Vendor-Class" "Aruba JL719C 8360" {
    option vendor-class-identifier "Aruba JL719C 8360";
    option aruba.image-file-name "ArubaOS-CX_8360-8100_10_13_1010.swi";
    option aruba.config-file-name "aoscx_dc_base.conf";
}

```

#### TFTP/HTTP Server (Out of Scope for This Role)

**Responsibilities:**

- Host generated base configurations
- (Optional) Host firmware images

**Directory Structure Example:**
```
/srv/tftp
├── ArubaOS-CX_6200_10_13_1040.swi
├── ArubaOS-CX_8360-8100_10_13_1010.swi
├── aoscx_base.conf
└── aoscx_dc_base.conf
```

### 4. Network Devices (Aruba CX Switches)

**Lifecycle Phases:**

1. **Factory Default** → DHCP request
2. **ZTP 1. Phase** → Download and compare firmware version
3. **ZTP 2. Phase** → Download and apply base config
4. **Bootstrap Complete** → Management connectivity established
5. **Ongoing Management** → Full configuration via Ansible

---

## Lifecycle Phases

### Phase 1: Planning and Documentation (NetBox)

**Objective:** Define the desired network state before any equipment arrives.

**Activities:**

**Site Planning**

- Create sites in NetBox
- Document racks and rack units
- Plan power distribution

**Device Documentation**

- Add devices to NetBox (can be pre-populated before physical arrival)
- Set device type, role, platform
- Record serial numbers (when known)
- Assign management IP addresses

**Network Design**

- Define VLANs and prefixes
- Create VRFs for multi-tenancy
- Plan IP addressing scheme
- Design routing topology (BGP AS, OSPF areas)

**Configuration Context**

- Set system-wide settings (NTP, DNS, timezone)
- Define site-specific or role-specific configurations
- Configure BGP fallback parameters

**Custom Fields**

- Set feature flags (device_bgp, device_evpn, device_vxlan, device_vsx)
- Tag devices for automation (ztp_ready, staging, production)

**Output:** Complete network design documented in NetBox.

---

### Phase 2: Staging of device

- Out of scope for this role

---

### Phase 3: Physical Installation

**Objective:** Install equipment in data center or network closet.

**Activities:**

**Physical Installation** (Documented in NetBox)

- Mount devices in racks
- Connect power cables (document in NetBox)
- Connect network cables (document in NetBox)
- Connect management interface to ZTP network

---

### Phase 4: Full Configuration Deployment (Ansible)

**Objective:** Apply complete network configuration from NetBox.

**Prerequisites:**

- Device accessible via management IP
- SSH/HTTPS enabled
- Admin credentials configured

**Process:**

```bash
# Deploy full configuration to all devices
ansible-playbook -i netbox_inventory.yml site.yml

# Or specific devices
ansible-playbook -i netbox_inventory.yml site.yml --limit sw01-lab

# Or specific features
ansible-playbook -i netbox_inventory.yml site.yml --tags vlans,bgp
```

**Configuration Applied:**

- ✅ Base system (NTP, DNS, timezone, banner)
- ✅ VRFs
- ✅ VLANs
- ✅ Physical interfaces (enable/disable, descriptions)
- ✅ LAG interfaces (LACP)
- ✅ L2 interfaces (access/trunk ports)
- ✅ L3 interfaces (IP addresses, VRF attachment)
- ✅ Loopback interfaces
- ✅ EVPN/VXLAN (if enabled)
- ✅ BGP configuration (if enabled)
- ✅ OSPF configuration (if enabled)
- ✅ VSX virtual chassis (if enabled)

**Key Features:**

- **Idempotent:** Safe to run multiple times
- **NetBox-driven:** All config from NetBox
- **Feature flags:** Control what gets configured via custom fields
- **Validation:** Automatic verification of applied configuration

---

### Phase 5: Ongoing Management

**Objective:** Maintain network configuration in sync with NetBox.

**Activities:**

**Configuration Changes**

```
Change Request → Update NetBox → Run Ansible → Verify
```

**Idempotent Mode**

```yaml
aoscx_idempotent_mode: true
```

- Adds configurations from NetBox
- **Removes** configurations not in NetBox
- Ensures switches match NetBox exactly

**Regular Synchronization**

```bash
# Daily/weekly scheduled job
ansible-playbook -i netbox_inventory.yml site.yml
```

**Change Validation**

- Ansible reports changes made
- Compare before/after state
- Rollback if needed

**Documentation Updates**

- Update NetBox when changes occur
- NetBox remains authoritative source
- Audit trail of all changes

---

## Data Flow

### Initial Deployment Flow

```mermaid
graph TB
    Start([👤 Engineer]) --> NB1["NetBox<br/>Document network design<br/>(devices, IPs, VLANs, routing)"]

    NB1 --> SW2["Switch (Base Config)<br/>Management connectivity established<br/>✅ Hostname, IP, SSH, HTTPS configured"]

    SW2 --> ANS2["Ansible Role<br/>Apply full configuration<br/><code>ansible-playbook site.yml</code>"]

    ANS2 --> SW3["Switch (Full Config)<br/>✅ Production ready<br/>All features configured"]

    style Start fill:#e1f5ff,stroke:#3f51b5,stroke-width:2px
    style NB1 fill:#e1f5ff,stroke:#3f51b5,stroke-width:2px
    style SW2 fill:#e8f5e9,stroke:#4caf50,stroke-width:2px
    style ANS2 fill:#fff4e1,stroke:#ff9800,stroke-width:2px
    style SW3 fill:#c8e6c9,stroke:#4caf50,stroke-width:3px
```

### Ongoing Management Flow

```mermaid
graph TB
    CR["📋 Change Request<br/>1. Change approved"] --> NB["🎯 NetBox<br/>2. Update NetBox<br/>(add VLAN, change IP, etc.)"]

    NB --> ANS["⚙️ Ansible Role<br/>3. Run Ansible playbook<br/><code>ansible-playbook site.yml</code>"]

    ANS --> Q1["Query NetBox for current state"]
    ANS --> Q2["Compare with switch state"]
    ANS --> Q3["Generate configuration changes"]
    ANS --> Q4["Apply changes to switch"]
    ANS --> Q5["Verify changes"]

    Q1 & Q2 & Q3 & Q4 & Q5 --> SW["🔌 Switch<br/>4. Configuration updated"]

    SW --> VER{"5. Validate change<br/>(monitoring, testing)"}

    VER -->|✅ Success| DOC["📚 Document<br/>6. Update documentation<br/>(NetBox already updated)"]
    VER -->|❌ Issue| NB

    DOC --> END([✅ Complete])

    style CR fill:#e1f5ff,stroke:#3f51b5,stroke-width:2px
    style NB fill:#e1f5ff,stroke:#3f51b5,stroke-width:2px
    style ANS fill:#fff4e1,stroke:#ff9800,stroke-width:2px
    style Q1 fill:#fff9c4,stroke:#fbc02d,stroke-width:1px
    style Q2 fill:#fff9c4,stroke:#fbc02d,stroke-width:1px
    style Q3 fill:#fff9c4,stroke:#fbc02d,stroke-width:1px
    style Q4 fill:#fff9c4,stroke:#fbc02d,stroke-width:1px
    style Q5 fill:#fff9c4,stroke:#fbc02d,stroke-width:1px
    style SW fill:#f3e5f5,stroke:#9c27b0,stroke-width:2px
    style VER fill:#ffe1e1,stroke:#f44336,stroke-width:2px
    style DOC fill:#e8f5e9,stroke:#4caf50,stroke-width:2px
    style END fill:#c8e6c9,stroke:#4caf50,stroke-width:3px
```

---

## Integration Points

### NetBox API Integration

**Authentication:**

```yaml
netbox_url: https://netbox.example.com
netbox_token: "{{ vault_netbox_token }}"
```

**Queried Objects:**

- Devices (filtered by tags, roles, sites)
- Interfaces (physical, virtual, LAG)
- IP addresses
- VLANs and prefixes
- VRFs
- Config context
- Custom fields
- Tags
- BGP sessions (netbox-bgp plugin)

**Dynamic Inventory:**

```bash
# Use NetBox as dynamic inventory source
ansible-playbook -i netbox_inventory.yml site.yml
```

### Collections Used

**Required Collections:**

- `arubanetworks.aoscx` >= 4.4.0 - Aruba CX modules
- `netbox.netbox` >= 3.21.0 - NetBox inventory and modules

**Python Libraries:**

- `pyaoscx` - Aruba CX SDK
- `pynetbox` - NetBox API client

### External Systems (Out of Scope)

While not managed by this role, integration points exist for:

**Monitoring Systems** (Prometheus, SNMP)

- Switch metrics and health
- Interface statistics
- BGP/OSPF status

**Logging Systems** (Syslog, ELK)

- Configuration changes
- System events
- Security logs

**Backup Systems**

- Configuration backups
- Automated snapshots before changes

**CI/CD Pipelines**

- Automated testing of configuration changes
- Rollback procedures
- Change approval workflows

---

## Best Practices

### 1. NetBox as Single Source of Truth

**Do:**

- ✅ Always update NetBox first, then run Ansible
- ✅ Use config context for site/role-specific settings
- ✅ Tag devices appropriately (production, staging, ztp_ready)
- ✅ Document physical infrastructure even if not used for automation
- ✅ Use custom fields for feature flags

**Don't:**

- ❌ Make manual changes to switches without updating NetBox
- ❌ Store configuration in multiple places
- ❌ Bypass NetBox for "quick fixes"

### 2. Idempotent Operations

**Do:**

- ✅ Run Ansible regularly (daily/weekly)
- ✅ Enable idempotent mode in production
  ```yaml
  aoscx_idempotent_mode: true
  ```
- ✅ Use `--check` mode to preview changes
- ✅ Test changes in staging environment first

**Don't:**

- ❌ Fear running Ansible multiple times
- ❌ Make manual changes that conflict with NetBox

### 3. Change Management

**Process:**

```
1. Create change request
2. Update NetBox (staging)
3. Test with Ansible in lab/staging
4. Approve change
5. Update NetBox (production)
6. Run Ansible in production
7. Verify and document
```

**Do:**

- ✅ Use version control for Ansible playbooks
- ✅ Tag production-ready devices appropriately
- ✅ Maintain separate staging environment
- ✅ Use `--limit` and `--tags` for targeted changes
- ✅ Review Ansible output for unexpected changes

**Don't:**

- ❌ Skip testing in staging
- ❌ Run massive changes without review
- ❌ Ignore Ansible warnings or errors

### 4. Security

**Do:**

- ✅ Use Ansible Vault for all credentials
  ```bash
  ansible-vault create group_vars/all/vault.yml
  ```
- ✅ Rotate passwords regularly
- ✅ Use SSH keys where possible
- ✅ Restrict Ansible controller access
- ✅ Audit NetBox access logs
- ✅ Use HTTPS for NetBox API

**Don't:**

- ❌ Store passwords in plain text
- ❌ Use same password across all devices
- ❌ Share Ansible Vault passwords insecurely

### 5. Documentation

**NetBox Documentation:**

- Device serial numbers
- Cable connections (even if not used for config)
- Rack locations
- Power connections
- Circuit IDs
- Contact information

**Ansible Documentation:**

- Playbook usage examples
- Variable definitions
- Custom filters and plugins
- Troubleshooting guides

**Why Document Physical Infrastructure?**

Even though physical documentation isn't used for automation:

- Essential for troubleshooting
- Required for disaster recovery
- Helps plan capacity
- Assists with maintenance
- Provides complete network picture

---

## Troubleshooting

### Configuration Issues

**Problem:** Ansible can't connect to device

- Verify device is in NetBox
- Check management IP reachability
- Confirm SSH/HTTPS is enabled
- Validate credentials

**Problem:** Changes not applied

- Check Ansible output for errors
- Verify NetBox data is correct
- Review custom fields and tags
- Check idempotent mode setting

**Problem:** Unexpected configuration removed

- Check idempotent mode is desired
- Verify all required config is in NetBox
- Review Ansible diff output before applying

---

## Summary

This network automation ecosystem provides:

- ✅ **Single Source of Truth:** NetBox contains all network design and configuration
- ✅ **Automated Deployment:** ZTP for initial setup, Ansible for full configuration
- ✅ **Idempotent State:** Switches automatically sync with NetBox
- ✅ **Complete Lifecycle:** From planning through ongoing management
- ✅ **Scalability:** Handle hundreds of switches from single control point
- ✅ **Auditability:** All changes tracked through NetBox and Ansible

The `aopdal.aruba_cx_switch` role is a key component in this ecosystem, bridging NetBox (source of truth) with Aruba CX switches (network infrastructure).

---

## Related Documentation

- [NETBOX_INTEGRATION.md](NETBOX_INTEGRATION.md) - NetBox configuration and custom fields
- [QUICKSTART.md](QUICKSTART.md) - Getting started with the role
- [REQUIREMENTS.md](REQUIREMENTS.md) - Required software and libraries
- [EVPN_VXLAN_CONFIGURATION.md](EVPN_VXLAN_CONFIGURATION.md) - EVPN/VXLAN fabric setup
- [BGP_CONFIGURATION.md](BGP_CONFIGURATION.md) - BGP configuration options
