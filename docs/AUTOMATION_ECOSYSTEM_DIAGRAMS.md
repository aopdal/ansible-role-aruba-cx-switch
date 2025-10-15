# Network Automation Ecosystem - Visual Reference

This document provides simplified visual diagrams for the automation ecosystem.

## Quick Reference Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    NETWORK AUTOMATION FLOW                       │
└─────────────────────────────────────────────────────────────────┘

PHASE 1: PLANNING
┌─────────────┐
│   NetBox    │  Engineer documents network design
│  (Plan)     │  • Devices, IPs, VLANs, routing
└──────┬──────┘  • Config context, custom fields
       │
       │ Query API
       ▼
PHASE 2: ZTP GENERATION
┌─────────────┐
│   Ansible   │  ansible-playbook generate-ztp-configs.yml
│  (Generate) │  → ztp_configs/sw01-lab_ztp_base.cfg
└──────┬──────┘
       │
       │ Copy to server
       ▼
PHASE 3: ZTP INFRASTRUCTURE
┌─────────────┐
│ DHCP/TFTP   │  Hosts ZTP scripts and base configs
│   Server    │  (Out of scope for this role)
└──────┬──────┘
       │
       │ New switch boots
       ▼
PHASE 4: DEVICE BOOTSTRAP
┌─────────────┐
│   Switch    │  1. DHCP → gets IP + ZTP URL
│    (ZTP)    │  2. Downloads ZTP script
└──────┬──────┘  3. Downloads base config
       │         4. Applies config → mgmt ready
       │
       │ SSH/HTTPS now available
       ▼
PHASE 5: FULL CONFIGURATION
┌─────────────┐
│   Ansible   │  ansible-playbook site.yml
│  (Deploy)   │  → Full config from NetBox
└──────┬──────┘
       │
       ▼
PHASE 6: PRODUCTION
┌─────────────┐
│   Switch    │  Fully configured and operational
│ (Production)│  All features active
└──────┬──────┘
       │
       │ Ongoing management
       ▼
PHASE 7: CHANGE MANAGEMENT
┌─────────────┐
│   NetBox    │  Update NetBox
│  (Change)   │  ↓
└──────┬──────┘  Run Ansible
       │         ↓
┌─────────────┐  Switch updated
│   Switch    │  ↓
│  (Updated)  │  Verify change
└─────────────┘
```

## Component Responsibilities

```
╔═══════════════════════════════════════════════════════════════╗
║                         NETBOX (SOUCE OF TRUTH)                ║
╠═══════════════════════════════════════════════════════════════╣
║ IN SCOPE FOR AUTOMATION:                                       ║
║ • Device info (hostname, platform, mgmt IP)                   ║
║ • Interfaces (physical, LAG, SVI, loopback)                   ║
║ • VLANs and VRFs                                              ║
║ • IP addresses                                                 ║
║ • Routing (BGP, OSPF)                                         ║
║ • EVPN/VXLAN config                                           ║
║ • Config context (NTP, DNS, timezone)                         ║
║ • Custom fields (feature flags)                               ║
║ • Tags (automation control)                                    ║
╠═══════════════════════════════════════════════════════════════╣
║ OUT OF SCOPE (But important to document):                     ║
║ • Physical: Cables, racks, power                             ║
║ • Site: Location, contact info                               ║
║ • Assets: Purchase orders, warranties                         ║
║ • Circuits: WAN links, ISP details                           ║
╚═══════════════════════════════════════════════════════════════╝

╔═══════════════════════════════════════════════════════════════╗
║              ANSIBLE ROLE (aopdal.aruba_cx_switch)            ║
╠═══════════════════════════════════════════════════════════════╣
║ RESPONSIBILITIES:                                              ║
║ • Query NetBox API                                            ║
║ • Generate ZTP base configs                                   ║
║ • Deploy full configurations                                  ║
║ • Maintain idempotent state                                   ║
║ • Handle: VLANs, L2/L3, EVPN, VXLAN, BGP, OSPF, VSX        ║
╠═══════════════════════════════════════════════════════════════╣
║ NOT RESPONSIBLE FOR:                                          ║
║ • DHCP server configuration                                   ║
║ • TFTP/HTTP server setup                                      ║
║ • ZTP script deployment                                       ║
║ • Firmware management                                         ║
║ • Backup/restore (use separate roles)                        ║
╚═══════════════════════════════════════════════════════════════╝

╔═══════════════════════════════════════════════════════════════╗
║               ZTP INFRASTRUCTURE (OUT OF SCOPE)                ║
╠═══════════════════════════════════════════════════════════════╣
║ DHCP SERVER:                                                   ║
║ • Provide IP, gateway, DNS to new switches                    ║
║ • Provide ZTP script URL (option 66/67)                       ║
║                                                                ║
║ TFTP/HTTP SERVER:                                             ║
║ • Host ZTP scripts                                            ║
║ • Host generated base configs (from Ansible)                  ║
║ • (Optional) Host firmware images                             ║
╚═══════════════════════════════════════════════════════════════╝
```

## Data Flow: Initial Deployment

```
NetBox                 Ansible              ZTP Server           Switch
  │                       │                     │                  │
  │                       │                     │                  │
  │ 1. Engineer          │                     │                  │
  │    documents         │                     │                  │
  │    network           │                     │                  │
  │◄───────────────────  │                     │                  │
  │                       │                     │                  │
  │                       │                     │                  │
  │  2. Query NetBox API  │                     │                  │
  ├──────────────────────►│                     │                  │
  │      (Device info)    │                     │                  │
  │                       │                     │                  │
  │                       │ 3. Generate ZTP     │                  │
  │                       │    base configs     │                  │
  │                       │                     │                  │
  │                       │ 4. Copy configs     │                  │
  │                       ├────────────────────►│                  │
  │                       │                     │                  │
  │                       │                     │  5. Power on     │
  │                       │                     │  6. DHCP request │
  │                       │                     │◄─────────────────┤
  │                       │                     │                  │
  │                       │                     │  7. IP + ZTP URL │
  │                       │                     ├─────────────────►│
  │                       │                     │                  │
  │                       │                     │  8. Download     │
  │                       │                     │     ZTP script   │
  │                       │                     │◄─────────────────┤
  │                       │                     │                  │
  │                       │                     │  9. Download     │
  │                       │                     │     base config  │
  │                       │                     │◄─────────────────┤
  │                       │                     │                  │
  │                       │                     │  10. Apply config│
  │                       │                     │                  │
  │                       │                     │  11. Reboot      │
  │                       │                     │                  │
  │                       │                     │                  │
  │                       │ 12. SSH/HTTPS now available           │
  │  13. Query NetBox API │                     │                  │
  ├──────────────────────►│                     │                  │
  │   (Full config data)  │                     │                  │
  │                       │                     │                  │
  │                       │ 14. Deploy full config                │
  │                       ├───────────────────────────────────────►│
  │                       │     (SSH/HTTPS)     │                  │
  │                       │                     │                  │
  │                       │ 15. ✅ Complete     │                  │
  │                       │                     │                  │
```

## Data Flow: Ongoing Management

```
Change Request → NetBox → Ansible → Switch → Verify
      │             │         │         │        │
      │             │         │         │        │
      └─────────────┴─────────┴─────────┴────────┘
              Continuous synchronization
```

## Network Topologies Supported

### Simple Access Network
```
┌───────────────┐
│   Core        │
│   Switch      │
│   (BGP/OSPF)  │
└───┬───┬───┬───┘
    │   │   │
┌───┴┐ ┌┴───┴──┐
│Acc1│ │ Acc2  │  Access switches
│    │ │       │  (L2 + VLANs)
└────┘ └───────┘
```

### EVPN/VXLAN Fabric
```
┌─────────┐         ┌─────────┐
│ Spine 1 │◄───────►│ Spine 2 │
│ (BGP)   │         │ (BGP)   │
└───┬─────┘         └─────┬───┘
    │  \             /  │
    │   \           /   │
    │    \         /    │
    │     \       /     │
┌───┴──┐  \     /  ┌───┴──┐
│Leaf 1│   \   /   │Leaf 2│
│(EVPN)│    \ /    │(EVPN)│
│      │     X     │      │
│      │    / \    │      │
└──────┘   /   \   └──────┘
          /     \
    Servers     Servers
```

### VSX Pair
```
┌──────────┐  ISL  ┌──────────┐
│ Switch 1 │◄─────►│ Switch 2 │
│  (VSX)   │  VSL  │  (VSX)   │
└────┬─────┘       └─────┬────┘
     │                   │
     └──────┬───┬────────┘
            │   │
      Dual-homed LAG
            │   │
        ┌───┴───┴───┐
        │  Server   │
        └───────────┘
```

## Feature Interaction Matrix

```
┌──────────┬──────┬──────┬──────┬──────┬─────┬─────┐
│ Feature  │ BGP  │ OSPF │ EVPN │VXLAN │ VSX │VRFs │
├──────────┼──────┼──────┼──────┼──────┼─────┼─────┤
│ BGP      │  ●   │  ○   │  ●   │  ○   │  ●  │  ●  │
│ OSPF     │  ○   │  ●   │  ×   │  ×   │  ●  │  ●  │
│ EVPN     │  ●   │  ×   │  ●   │  ●   │  ●  │  ○  │
│ VXLAN    │  ○   │  ×   │  ●   │  ●   │  ●  │  ○  │
│ VSX      │  ●   │  ●   │  ●   │  ●   │  ●  │  ●  │
│ VRFs     │  ●   │  ●   │  ○   │  ○   │  ●  │  ●  │
└──────────┴──────┴──────┴──────┴──────┴─────┴─────┘

Legend:
● = Required/Strongly recommended
○ = Compatible/Optional
× = Incompatible/Not supported together
```

## Troubleshooting Decision Tree

```
Switch not responding?
│
├─ Can't reach mgmt IP?
│  ├─ Check physical: Cable, port, power
│  ├─ Check DHCP: IP assigned?
│  └─ Check ZTP: Config applied?
│
├─ Can reach but Ansible fails?
│  ├─ SSH enabled? → Check ZTP config
│  ├─ Credentials? → Check vault
│  └─ In NetBox? → Add device
│
└─ Config not as expected?
   ├─ NetBox data correct? → Fix NetBox
   ├─ Feature flags set? → Check custom fields
   ├─ Idempotent mode? → Check if configs removed
   └─ Run with -vvv → Review detailed output
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
