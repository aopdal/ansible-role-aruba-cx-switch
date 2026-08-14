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
        Role["aopdal.aruba_cx_switch Role<br/><br/>Responsibilities:<br/>• Query NetBox API<br/>• Apply full configurations<br/>• Maintain idempotent state<br/>• Handle EVPN/VXLAN, BGP, OSPF, VSX, STP, port-access, static routes"]
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

### Network Topologies Supported

The role supports several common topologies out of the box:

#### Simple Access Network

```mermaid
graph TB
    Core["Core Switch<br/>BGP/OSPF"]
    Acc1["Access Switch 1<br/>L2 + VLANs"]
    Acc2["Access Switch 2<br/>L2 + VLANs"]

    Core --> Acc1
    Core --> Acc2

    style Core fill:#e1f5ff,stroke:#3f51b5,stroke-width:2px
    style Acc1 fill:#e1ffe1,stroke:#4caf50,stroke-width:2px
    style Acc2 fill:#e1ffe1,stroke:#4caf50,stroke-width:2px
```

#### EVPN/VXLAN Fabric

```mermaid
graph TB
    S1["Spine 1<br/>BGP Route Reflector"]
    S2["Spine 2<br/>BGP Route Reflector"]
    L1["Leaf 1<br/>EVPN VTEP"]
    L2["Leaf 2<br/>EVPN VTEP"]
    Srv1["Servers<br/>Rack 1"]
    Srv2["Servers<br/>Rack 2"]

    S1 <--> L1
    S1 <--> L2
    S2 <--> L1
    S2 <--> L2

    L1 --> Srv1
    L2 --> Srv2

    style S1 fill:#e1f5ff,stroke:#3f51b5,stroke-width:2px
    style S2 fill:#e1f5ff,stroke:#3f51b5,stroke-width:2px
    style L1 fill:#e1ffe1,stroke:#4caf50,stroke-width:2px
    style L2 fill:#e1ffe1,stroke:#4caf50,stroke-width:2px
    style Srv1 fill:#f0f0f0,stroke:#9e9e9e,stroke-width:2px
    style Srv2 fill:#f0f0f0,stroke:#9e9e9e,stroke-width:2px
```

#### VSX Pair

```mermaid
graph TB
    SW1["Switch 1<br/>VSX Primary"]
    SW2["Switch 2<br/>VSX Secondary"]
    SRV["Server<br/>Dual-homed LAG"]

    SW1 <-->|ISL/VSL Keepalive| SW2
    SW1 -->|LAG Member 1| SRV
    SW2 -->|LAG Member 2| SRV

    style SW1 fill:#e1f5ff,stroke:#3f51b5,stroke-width:2px
    style SW2 fill:#e1f5ff,stroke:#3f51b5,stroke-width:2px
    style SRV fill:#e1ffe1,stroke:#4caf50,stroke-width:2px
```

---

## Components and Responsibilities

### 1. NetBox (Source of Truth)

**Scope: Complete Network Inventory and Configuration Data**

```mermaid
graph LR
    subgraph "NetBox - IN SCOPE FOR AUTOMATION"
        A1[Device Info<br/>hostname, platform, mgmt IP]
        A2[Interfaces<br/>physical, LAG, SVI, loopback]
        A3[VLANs and VRFs]
        A4[IP Addresses]
        A5[Routing<br/>BGP, OSPF]
        A6[EVPN/VXLAN Config]
        A7[Config Context<br/>NTP, DNS, timezone]
        A8[Custom Fields<br/>feature flags]
        A9[Tags<br/>automation control]
    end

    subgraph "NetBox - OUT OF SCOPE"
        B1[Physical: Cables, racks, power]
        B2[Site: Location, contact info]
        B3[Assets: Purchase orders, warranties]
        B4[Circuits: WAN links, ISP details]
    end

    style A1 fill:#e1f5ff
    style A2 fill:#e1f5ff
    style A3 fill:#e1f5ff
    style A4 fill:#e1f5ff
    style A5 fill:#e1f5ff
    style A6 fill:#e1f5ff
    style A7 fill:#e1f5ff
    style A8 fill:#e1f5ff
    style A9 fill:#e1f5ff
    style B1 fill:#f0f0f0
    style B2 fill:#f0f0f0
    style B3 fill:#f0f0f0
    style B4 fill:#f0f0f0
```

#### In Scope (Used by This Role)

- ✅ **Device Information**: Hostname, platform, serial number, management IP
- ✅ **Interfaces**: Physical ports, LAGs, SVIs, loopbacks
- ✅ **L2 Configuration**: VLANs, trunk/access ports, allowed VLANs
- ✅ **L3 Configuration**: IP addresses, VRFs, routing
- ✅ **Routing Protocols**: BGP (via netbox-bgp plugin), OSPF areas
- ✅ **EVPN/VXLAN**: VNI mappings, EVPN instance configuration
- ✅ **Virtual Chassis**: VSX configuration data
- ✅ **Config Context**: System settings (NTP, DNS, timezone, banner)
- ✅ **Custom Fields**: Feature flags (device_evpn, device_vxlan, device_vsx, device_ospf, device_anycast_gateway) — BGP is not gated by a custom field; it is configured only via the NetBox BGP plugin, gated by `netbox_bgp_plugin_available` and `device_bgp_sessions | length > 0`
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
- ✅ Handle complex features (EVPN, VXLAN, BGP, OSPF, VSX, STP, port-access, static routes)
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

*ZTP config generation is not part of this Ansible role, but the phase is included in the diagram below for completeness.*

```mermaid
graph TD
    A[PHASE 1: PLANNING<br/>NetBox] -->|Engineer documents network design<br/>Devices, IPs, VLANs, routing<br/>Config context, custom fields| B[PHASE 2: ZTP GENERATION<br/>Ansible]
    B -->|ansible-playbook generate-ztp-configs.yml<br/>→ ztp_configs/sw01-lab_ztp_base.cfg| C[PHASE 3: ZTP INFRASTRUCTURE<br/>DHCP/TFTP Server]
    C -->|Copy ZTP configs to server<br/>Out of scope for this role| D[PHASE 4: DEVICE BOOTSTRAP<br/>Switch ZTP]
    D -->|1. DHCP → gets IP + ZTP URL<br/>2. Downloads ZTP script<br/>3. Downloads base config<br/>4. Applies config → mgmt ready| E[PHASE 5: FULL CONFIGURATION<br/>Ansible Deploy]
    E -->|ansible-playbook site.yml<br/>→ Full config from NetBox<br/>SSH/HTTPS now available| F[PHASE 6: PRODUCTION<br/>Switch in Production]
    F -->|Ongoing management| G[PHASE 7: CHANGE MANAGEMENT<br/>Update NetBox]
    G -->|Run Ansible playbook| H[Switch Updated]
    H -->|Verify change| F

    style A fill:#e1f5ff
    style B fill:#fff4e1
    style C fill:#ffe1e1
    style D fill:#e1ffe1
    style E fill:#fff4e1
    style F fill:#e1f5e1
    style G fill:#e1f5ff
    style H fill:#e1ffe1
```

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

- Set feature flags (device_evpn, device_vxlan, device_vsx, device_ospf, device_anycast_gateway)
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

A more detailed, actor-by-actor view of the same flow:

```mermaid
sequenceDiagram
    participant E as Engineer
    participant N as NetBox
    participant A as Ansible
    participant Z as ZTP Server
    participant S as Switch

    Note over E,N: Phase 1: Planning
    E->>N: 1. Document network design<br/>(devices, IPs, VLANs, routing)

    Note over N,A: Phase 2: ZTP Generation
    A->>N: 2. Query NetBox API<br/>(device info)
    N-->>A: Device data
    A->>A: 3. Generate ZTP base configs
    A->>Z: 4. Copy configs to ZTP server

    Note over Z,S: Phase 3: Device Bootstrap
    S->>Z: 5. Power on<br/>6. DHCP request
    Z->>S: 7. IP + ZTP URL
    S->>Z: 8. Download ZTP script
    S->>Z: 9. Download base config
    S->>S: 10. Apply config<br/>11. Reboot

    Note over N,S: Phase 4: Full Configuration
    A->>N: 12. Query NetBox API<br/>(full config data)
    N-->>A: Complete configuration
    A->>S: 13. Deploy full config<br/>(SSH/HTTPS now available)
    S-->>A: 14. ✅ Configuration applied
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

- `arubanetworks.aoscx` >= 4.5.1 - Aruba CX modules
- `netbox.netbox` >= 3.23.0 - NetBox inventory and modules

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

```mermaid
graph TD
    A[Switch not responding?] --> B{Can't reach mgmt IP?}
    B -->|Yes| C[Check Physical]
    B -->|No| D{Can reach but Ansible fails?}

    C --> C1[Cable, port, power]
    C --> C2[DHCP: IP assigned?]
    C --> C3[ZTP: Config applied?]

    D --> D1{SSH enabled?}
    D1 -->|No| D1A[Check ZTP config]
    D1 -->|Yes| D2{Credentials valid?}
    D2 -->|No| D2A[Check vault]
    D2 -->|Yes| D3{Device in NetBox?}
    D3 -->|No| D3A[Add device to NetBox]

    B -->|Config issues| E{Config not as expected?}
    E --> E1{NetBox data correct?}
    E1 -->|No| E1A[Fix NetBox data]
    E1 -->|Yes| E2{Feature flags set?}
    E2 -->|No| E2A[Check custom fields]
    E2 -->|Yes| E3{Idempotent mode?}
    E3 -->|Yes| E3A[Check if configs removed]
    E3 -->|No| E4[Run with -vvv for details]

    style A fill:#ffe1e1
    style C1 fill:#fff4e1
    style C2 fill:#fff4e1
    style C3 fill:#fff4e1
    style D1A fill:#fff4e1
    style D2A fill:#fff4e1
    style D3A fill:#fff4e1
    style E1A fill:#e1f5ff
    style E2A fill:#e1f5ff
    style E3A fill:#fff4e1
    style E4 fill:#e1ffe1
```

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
