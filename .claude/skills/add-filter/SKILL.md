---
name: add-filter
description: How to add or change a Jinja filter in the aopdal.aruba_cx_switch role — implementation in netbox_filters_lib/, registration in filter_plugins/netbox_filters.py, pytest unit tests, and filter docs. Use when creating, renaming or changing a filter, or when moving logic out of YAML/Jinja into Python.
---

# Add or change a filter

## 1. Implement

- Put the function in `netbox_filters_lib/<topic>.py`. Reuse an existing
  topic module if one fits (`vlan_filters`, `vrf_filters`, `ospf_filters`,
  `bgp_filters`, `snmp_filters`, `central_filters`, `interface_*`,
  `l3_config_helpers`, `utils`, ...). New module only for a new topic.
- The library lives outside `filter_plugins/` on purpose: Ansible's
  plugin loader would otherwise try to load each file as a plugin.
- Pure function: no I/O, no global state, no Ansible imports. Accept
  missing/None inputs gracefully (NetBox fields are often null).
- NetBox 4.7 choice fields can come as `{"value": ..., "label": ...}`
  dicts or plain strings — read them with `nb_choice_value` from
  `netbox_filters_lib/utils.py`.
- Management VRF: use `resolve_mgmt_vrf` (`netbox_filters_lib/mgmt_vrf.py`),
  never NetBox `mgmt_only`.
- Return deterministic output (sort lists) so change detection is stable.
- Docstring describing inputs, output and an example.

## 2. Register

In `filter_plugins/netbox_filters.py`:

- Add the import to the matching `from netbox_filters_lib.<topic> import`
  block (import order is intentional, not alphabetical; keep it grouped).
- Add `"name": name` to the dict in `FilterModule.filters()`.
- REST fact transformations belong in `filter_plugins/rest_api_transforms.py`
  instead.

## 3. Test

- Add tests to `tests/unit/test_<topic>.py` (create it if new). Use
  class-per-function style (`class TestMyFilter:`) like the existing files,
  and trimmed real payloads from REST / NetBox as fixtures.
- Cover: happy path, empty/None input, the "no change needed" case, and
  every branch that decides add vs. remove.
- Add the name to `EXPECTED_FILTER_NAMES` in
  `tests/unit/test_netbox_filters.py` (this test fails if the registry
  and the expected set differ).
- Run `make test-unit-quick` while iterating, `make test-unit` at the end.

## 4. Use it

- Call with pipe syntax in `set_fact`/templates:
  `{{ value | my_filter(arg) }}`. Never `lookup('my_filter', ...)` — that
  silently returns nothing.

## 5. Document

- Add or update the entry in `docs/FILTER_PLUGINS.md`; if the filter is
  generally reusable, also `docs/FILTER_PLUGINS_REUSE.md`.
- Behaviour change visible to users → `CHANGELOG.md` `[Unreleased]`.
