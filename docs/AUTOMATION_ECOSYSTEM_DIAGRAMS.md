# Network Automation Ecosystem - Visual Reference

This document provides simplified visual diagrams for the automation ecosystem.

## Quick Reference Diagram

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

## Component Responsibilities

### NetBox (Source of Truth)

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

### Ansible Role (aopdal.aruba_cx_switch)

**RESPONSIBILITIES:**

- Query NetBox API
- Transform NetBox data into Aruba CX CLI
- Generate Jinja2 templates
- Execute arubanetworks.aoscx collection modules
- Manage configuration lifecycle
- Generate ZTP base configs (before devices exist)

### ZTP Infrastructure (DHCP/TFTP Server)

**OUT OF SCOPE** for this role, but critical for the ecosystem:

- Host ZTP scripts and base configs
- DHCP option configuration (ZTP URL)
- TFTP/HTTP file serving

### Aruba CX Switch

**RESPONSIBILITIES:**

- Execute ZTP process on first boot
- Accept configuration via SSH/HTTPS
- Report status and health

---

## Detailed Data Flow: ZTP to Production

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

---

## Data Flow: Ongoing Change Management

```mermaid
graph LR
    A[Change Request] --> B[Update NetBox]
    B --> C[Run Ansible Playbook]
    C --> D[Deploy to Switch]
    D --> E[Verify Change]
    E -->|Success| F[Complete]
    E -->|Issue| B

    style A fill:#e1f5ff
    style B fill:#fff4e1
    style C fill:#fff4e1
    style D fill:#e1ffe1
    style E fill:#ffe1e1
    style F fill:#e1f5e1
```

---

## Network Topologies Supported

### Simple Access Network

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

### EVPN/VXLAN Fabric

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

### VSX Pair

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

## Feature Interaction Matrix

| Feature | BGP | OSPF | EVPN | VXLAN | VSX | VRFs |
|---------|:---:|:----:|:----:|:-----:|:---:|:----:|
| **BGP**    | ● | ○ | ● | ○ | ● | ● |
| **OSPF**   | ○ | ● | ● | ● | ● | ● |
| **EVPN**   | ● | ● | ● | ● | ● | ○ |
| **VXLAN**  | ○ | ● | ● | ● | ● | ○ |
| **VSX**    | ● | ● | ● | ● | ● | ● |
| **VRFs**   | ● | ● | ○ | ○ | ● | ● |

**Legend:**

- ● = Required/Strongly recommended
- ○ = Compatible/Optional
- × = Incompatible/Not supported together

**Note:** OSPF is commonly used in EVPN/VXLAN fabrics for underlay routing (loopback reachability between leafs and spines), while eBGP handles the overlay (EVPN control plane).

---

## Troubleshooting Decision Tree

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

## Quick Command Reference

```bash
# Generate ZTP configs (no device connection needed)
ansible-playbook -i inventory.yml generate-ztp.yml

# Deploy full config to all devices
ansible-playbook -i netbox_inventory.yml site.yml

# Deploy to specific devices
ansible-playbook -i netbox_inventory.yml site.yml --limit sw01,sw02

# Deploy specific features only
ansible-playbook -i netbox_inventory.yml site.yml --tags vlans,bgp

# Check what would change (dry-run)
ansible-playbook -i netbox_inventory.yml site.yml --check --diff

# Enable idempotent mode (remove configs not in NetBox)
ansible-playbook -i netbox_inventory.yml site.yml -e aoscx_idempotent_mode=true

# Verbose output for troubleshooting
ansible-playbook -i netbox_inventory.yml site.yml -vvv
```

See [AUTOMATION_ECOSYSTEM.md](AUTOMATION_ECOSYSTEM.md) for complete details.
