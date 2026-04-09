# VLAN Workflow Visualization

## Configuration Phase Flow

```mermaid
graph TD
    A[Start: tasks/main.yml] --> B[identify_vlan_changes.yml]

    B --> B1[Fetch VLANs from NetBox]
    B1 --> B2[Gather device VLAN facts]
    B2 --> B3[Calculate vlans_in_use]
    B3 --> B4[Determine vlan_changes]
    B4 --> B5{Facts Set}

    B5 -->|vlans| C[configure_vlans.yml]
    B5 -->|vlans_in_use| D[configure_evpn.yml]
    B5 -->|vlan_changes| C
    B5 -->|vlans| D
    B5 -->|vlans_in_use| E[configure_vxlan.yml]
    B5 -->|vlans| E

    C --> C1[Assert prerequisites]
    C1 --> C2[Create VLANs]

    D --> D1[Assert prerequisites]
    D1 --> D2[Gather existing EVPN config]
    D2 --> D3[Filter VLANs needing EVPN]
    D3 --> D4[Configure EVPN]

    E --> E1[Assert prerequisites]
    E1 --> E2[Gather existing VXLAN config]
    E2 --> E3[Filter VLANs needing VXLAN]
    E3 --> E4[Configure VXLAN/VNI]

    C2 --> F[Interface Configuration]
    D4 --> F
    E4 --> F

    F --> G[End Configuration Phase]
```

## Cleanup Phase Flow (Idempotent Mode Only)

```mermaid
graph TD
    A[Start: Cleanup Phase] --> B[identify_vlan_changes.yml]

    B --> B1[Re-fetch VLANs from NetBox]
    B1 --> B2[Re-gather device VLAN facts]
    B2 --> B3[Re-calculate vlans_in_use]
    B3 --> B4[Re-determine vlan_changes]
    B4 --> B5{Facts Set}

    B5 -->|vlan_changes.vlans_to_delete| C[cleanup_evpn.yml]
    B5 -->|vlans| C

    C --> C1[Assert prerequisites]
    C1 --> C2[Filter VLANs to remove]
    C2 --> C3[Remove EVPN config]

    C3 --> D[cleanup_vxlan.yml]
    B5 -->|vlan_changes.vlans_to_delete| D
    B5 -->|vlans| D

    D --> D1[Assert prerequisites]
    D1 --> D2[Filter VLANs to remove]
    D2 --> D3[Remove VLAN from VNI]
    D3 --> D4[Remove VNI from VXLAN interface]

    D4 --> E[cleanup_vlans.yml]
    B5 -->|vlan_changes.vlans_to_delete| E

    E --> E1[Assert prerequisites]
    E1 --> E2[Delete VLANs]

    E2 --> F[End Cleanup Phase]
```

## Fact Dependencies

```mermaid
graph LR
    A[identify_vlan_changes.yml] -->|vlans| B[configure_vlans.yml]
    A -->|vlans| C[configure_evpn.yml]
    A -->|vlans| D[configure_vxlan.yml]
    A -->|vlans_in_use| C
    A -->|vlans_in_use| D
    A -->|vlan_changes| B

    A -->|vlan_changes.vlans_to_delete| E[cleanup_evpn.yml]
    A -->|vlan_changes.vlans_to_delete| F[cleanup_vxlan.yml]
    A -->|vlan_changes.vlans_to_delete| G[cleanup_vlans.yml]
    A -->|vlans| E
    A -->|vlans| F

    style A fill:#e1f5ff,stroke:#01579b,stroke-width:3px
    style B fill:#f3e5f5,stroke:#4a148c
    style C fill:#f3e5f5,stroke:#4a148c
    style D fill:#f3e5f5,stroke:#4a148c
    style E fill:#ffebee,stroke:#b71c1c
    style F fill:#ffebee,stroke:#b71c1c
    style G fill:#ffebee,stroke:#b71c1c
```

## Facts Reference Table

| Fact Name | Type | Set By | Used By | Purpose |
|-----------|------|--------|---------|---------|
| `vlans` | list[dict] | identify_vlan_changes.yml | configure_vlans, configure_evpn, configure_vxlan, cleanup_evpn, cleanup_vxlan | VLANs from NetBox (desired state) |
| `vlans_in_use` | dict | identify_vlan_changes.yml | configure_vlans, configure_evpn, configure_vxlan | VLANs currently used by interfaces |
| `vlans_in_use.vids` | list[int] | identify_vlan_changes.yml | configure_evpn, configure_vxlan | VLAN IDs in use |
| `vlan_changes` | dict | identify_vlan_changes.yml | configure_vlans, cleanup_* | Changes needed |
| `vlan_changes.vlans_to_create` | list[dict] | identify_vlan_changes.yml | configure_vlans | VLANs to create |
| `vlan_changes.vlans_to_delete` | list[int] | identify_vlan_changes.yml | cleanup_* | VLANs to delete |
| `vlan_changes.vlans_in_use` | list[int] | identify_vlan_changes.yml | Debug only | VLANs protected from deletion |
