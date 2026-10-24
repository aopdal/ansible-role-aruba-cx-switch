# HPE Aruba Networking Central configuration

The role can enable the AOS-CX connection to HPE Aruba Networking Central
(`hpe-anw-central`) per device, driven by a NetBox device tag. The intended
use is monitoring: the switch stays configured by this role from NetBox, and
Central only receives telemetry.

Task file: `tasks/configure_central.yml`. Filters:
`netbox_filters_lib/central_filters.py` (`has_device_tag`,
`get_central_changes`).

## Requirements

- AOS-CX 10.15 or later (the role's minimum), which uses the
  `hpe-anw-central` CLI context and the `/system/hpe_anw_central` REST
  resource. The older `aruba-central` context is not supported.
- The device must reach Central through its management path. The role does
  not configure the connection's VRF or location override; the device
  defaults are used. These work both with the out-of-band `mgmt` port and
  with in-band management.
- The device must be added to Central (subscription and group). Making it
  monitor-only is set up on the Central side; the device configuration has
  no monitor-only setting.

## Enabling Central for a device

Add the tag `hpe-anw-central-mon` to the device in NetBox. The NetBox
inventory plugin exposes device tags as the `tags` host variable:

```json
"tags": [
    "dhcp",
    "hpe-anw-central-mon"
],
```

The role then pushes:

```text
hpe-anw-central
    enable
```

AOS-CX does not show an enabled connection in the running-config; only the
disabled state is rendered:

```text
hpe-anw-central
    disable
```

This is also what the ZTP starting config (`templates/system.j2`) renders
for devices without the tag. With the tag, the template renders `enable`.

## Tested platforms

| Platform        | Management path                                         |
| --------------- | ------------------------------------------------------- |
| CX 8360         | Out-of-band `mgmt` port                                 |
| CX 6200 (VSF)   | In-band `vlan1`; `mgmt` port used for VSF split detection |
| CX 6000         | In-band (no `mgmt` port)                                |

## Variables

```yaml
aoscx_configure_central: true                   # feature toggle
aoscx_central_monitor_tag: hpe-anw-central-mon  # NetBox tag (slug or name)
```

Tags are matched on slug or name, case-insensitively.

## Behaviour

| Device has the tag | `aoscx_idempotent_mode` | Result                                 |
| ------------------ | ----------------------- | -------------------------------------- |
| yes                | any                     | Connection enabled                     |
| no                 | `false`                 | Left alone (task skipped)              |
| no                 | `true`                  | Connection disabled                    |

## Change detection

The enabled state is not rendered in the running-config, so `aoscx_config`
cannot diff an `enable` line by itself. The role reads the current state
first and only pushes when it differs:

- With REST fact gathering (`aoscx_gather_facts_rest_api: true`): the
  `disable` attribute of `/system/hpe_anw_central`, stored as
  `aoscx_central_facts`.
- Without REST facts (or when the REST query returns 404):
  `show running-config`. A `disable` line inside the `hpe-anw-central`
  context means disabled; no such line means enabled.

Run with `-v` (or `aoscx_debug: true`) to see the desired state, current
state, where it was read from, and the action taken.

## Tags

`central`, `base_config`, `system`:

```bash
ansible-playbook site.yml --tags central
```
