# How to Access the New VLAN Documentation

## Quick Access

### Option 1: MkDocs Site (Recommended) 🌐

**Start the documentation server:**

```bash
cd /workspaces/ansible-role-aruba-cx-switch
make docs-serve
# Opens at http://127.0.0.1:8000
```

**Navigate in the site:**

```
http://127.0.0.1:8000
  └─ Top Navigation: "Configuration" tab
      └─ Left Sidebar: "VLAN Management" section
          ├─ Workflow Overview          → VLAN_CHANGE_IDENTIFICATION_WORKFLOW.md
          ├─ Visual Diagrams            → VLAN_WORKFLOW_DIAGRAMS.md
          └─ Developer Guide            → VLAN_DEVELOPER_GUIDE.md
```

### Option 2: Direct File Access 📁

**From the repository root:**

```bash
# Main overview
cat docs/VLAN_CHANGE_IDENTIFICATION_WORKFLOW.md

# Visual diagrams
cat docs/VLAN_WORKFLOW_DIAGRAMS.md

# Developer quick reference
cat docs/VLAN_DEVELOPER_GUIDE.md
```

### Option 3: GitHub (when pushed) 🐙

**Navigate to:**

```
https://github.com/aopdal/ansible-role-aruba-cx-switch
  └─ docs/
      ├─ VLAN_CHANGE_IDENTIFICATION_WORKFLOW.md
      ├─ VLAN_WORKFLOW_DIAGRAMS.md
      └─ VLAN_DEVELOPER_GUIDE.md
```

## Documentation Structure

```
📚 Aruba CX Switch Ansible Role Documentation
│
├─ 🏠 Home (index.md)
│   └─ Configuration Guides section
│       └─ VLAN management workflow link
│
├─ 🚀 Getting Started
│   ├─ Quick Start
│   ├─ Requirements
│   └─ Development
│
├─ 🏗️ Architecture
│   ├─ Automation Ecosystem
│   └─ Visual Reference
│
├─ 🔌 NetBox Integration
│   ├─ Integration Reference
│   └─ Filter Plugins
│
├─ ⚙️ Configuration ← YOU ARE HERE
│   ├─ Base System
│   ├─ ZTP
│   │
│   ├─ 🎯 VLAN Management ← NEW SECTION
│   │   ├─ 📋 Workflow Overview
│   │   ├─ 📊 Visual Diagrams
│   │   └─ 👨‍💻 Developer Guide
│   │
│   ├─ EVPN & VXLAN
│   └─ BGP
│
├─ 🧪 Testing & Development
└─ 📖 Reference
```

## What Each Document Covers

### 📋 Workflow Overview

**File:** `VLAN_CHANGE_IDENTIFICATION_WORKFLOW.md`

**Audience:** DevOps Engineers, Network Automation Engineers

**Content:**

- Problem statement and solution
- Single source of truth architecture
- Task execution order (configuration + cleanup)
- Facts reference table
- Benefits and safety features
- Testing recommendations

**Best for:** Understanding the overall workflow

---

### 📊 Visual Diagrams

**File:** `VLAN_WORKFLOW_DIAGRAMS.md`

**Audience:** Visual learners, Architects, Team leads

**Content:**

- Mermaid flowcharts for configuration phase
- Mermaid flowcharts for cleanup phase
- Fact dependencies graph
- Before/after timeline comparison
- Facts reference table

**Best for:** Quick visual understanding

---

### 👨‍💻 Developer Guide

**File:** `VLAN_DEVELOPER_GUIDE.md`

**Audience:** Developers contributing to the role

**Content:**

- Quick reference patterns
- How to add new VLAN-related tasks
- Available facts and their structure
- Common filter patterns
- Debugging tips
- Testing checklist

**Best for:** Extending the role with new features

---

## Search Functionality

Use the search bar in the MkDocs site to find:

- **"vlan changes"** → All VLAN workflow docs
- **"identify_vlan_changes"** → Task file references
- **"vlans_in_use"** → Fact usage examples
- **"vlan_changes.vlans_to_delete"** → Cleanup patterns
- **"idempotent mode"** → Cleanup behavior

## Related Documentation

When reading VLAN documentation, you may also want to reference:

- **EVPN & VXLAN Configuration** - EVPN uses VLAN data
- **Filter Plugins** - VLAN transformation filters
- **Idempotent Mode** - VLAN cleanup behavior
- **BGP EVPN Fabric Example** - Complete fabric with VLANs

## Tips for Navigation

1. **Use the search** - MkDocs has powerful full-text search
2. **Follow cross-links** - Documents link to related topics
3. **Check diagrams first** - Visual overview before deep dive
4. **Keep developer guide handy** - Quick patterns when coding
5. **Compare workflows** - See before/after in Visual Diagrams

## Contributing

Found an issue or want to improve the documentation?

1. Edit the markdown files in `docs/`
2. Test locally: `make docs-serve`
3. Submit a pull request

See `docs/CONTRIBUTING.md` for details.

---

**Happy documenting! 📚✨**
