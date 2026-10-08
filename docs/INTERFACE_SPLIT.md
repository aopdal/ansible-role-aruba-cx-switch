# Interface split (breakout)

A high-speed port can be split into several lower-speed interfaces, for
example a 100G QSFP28 port into 4x 25G. On AOS-CX this is the `split`
command on the port; the device then creates the child interfaces
`<port>:1` ... `<port>:N`.

## Requirements

- NetBox 4.7 or later. NetBox 4.7 added the `channels` field on
  interfaces. Older NetBox versions have no such field, and the role then
  never splits a port - nothing else changes, so NetBox 4.6 keeps working.
- `aoscx_configure_physical_interfaces: true` and
  `aoscx_configure_interface_split: true` (both default).

## Modelling in NetBox

| Interface  | Field        | Value                         |
| ---------- | ------------ | ----------------------------- |
| `1/1/18`   | `channels`   | `4`                           |
| `1/1/18:1` | `parent`     | `1/1/18`                      |
| `1/1/18:1` | `channel_id` | `1` (`2`, `3`, `4` for the others) |

The children are normal physical interfaces (not `virtual`). Configure
them like any other port: enabled, MTU, LAG membership, L2 mode or IP
addresses.

Resulting device config:

```text
interface 1/1/18
    no shutdown
    split 4
    mtu 9198
interface 1/1/18:1
    no shutdown
    mtu 9198
    lag 101
interface 1/1/18:2
    no shutdown
    mtu 9198
    lag 101
```

## How the role applies it

The split runs at the start of the physical interface step
(`tasks/configure_interface_split.yml`, included from
`tasks/configure_physical_interfaces.yml`), before the port and its
children are configured, because the children only exist on the device
after the split.

1. Skipped entirely, with no extra device call, when no NetBox interface
   has a `channels` value.
2. Compares the device's split state with `channels`
   (`get_interfaces_to_split` filter). Ports that already have the right
   split are left alone, so reruns report no change. The device state
   comes from:
    - **REST API facts** (`aoscx_gather_facts_rest_api: true`): a separate
      query for `split_admin_status`, `split_children` and `split_parent`
      on `/system/interfaces`, stored as `aoscx_interface_split_facts`.
      These facts also show which ports can be split at all; a port with
      `channels` that cannot be split is skipped with a warning.
    - **Running-config** (fallback): `split <N>` lines from
      `show running-config`, used with `aoscx_facts`, or when the device
      rejects the split attributes (not all hardware supports splitting).
3. Pushes `split <N>` with `ansible.netcommon.cli_command` and answers the
   AOS-CX confirmation prompt. `aoscx_config` is not used because it
   cannot answer prompts.
4. AOS-CX clears the port config when it splits a port, so ports split in
   this run are re-enabled with their description and MTU from NetBox in
   the same run.

## REST API split attributes

Example from a CX 8325 (REST v10.18) with `1/1/18` split 4 and `1/1/17`
not split:

| Interface  | `split_admin_status` | `split_children` | `split_parent` |
| ---------- | -------------------- | ---------------- | -------------- |
| `1/1/1`    | `none`               | `{}`             | `null`         |
| `1/1/17`   | `active`             | `1/1/17:1`..`:4` | `null`         |
| `1/1/17:1` | `inactive`           | `{}`             | `1/1/17`       |
| `1/1/18`   | `inactive`           | `1/1/18:1`..`:4` | `null`         |
| `1/1/18:1` | `active`             | `{}`             | `1/1/18`       |

A splittable port always lists its possible children, split or not. A
split port is `inactive` itself and its children in use are `active`; the
split count is the number of `active` children. `none` (or `null` on LAGs)
means the interface cannot be split.

On a splittable port that is not split, the REST interface facts already
include the inactive children.

## Limitations

- **Splitting is disruptive.** It takes the port down and clears its
  config. Set `aoscx_configure_interface_split: false` to stop the role
  from splitting ports.
- **The role never removes a split.** Setting `channels` back to empty in
  NetBox does not push `no split`. Un-splitting deletes the child
  interfaces and their config, and NetBox 4.6 cannot express a split at
  all, so the role cannot tell "no split wanted" from "not modelled".
  Remove the split by hand.
- A bare `split` (platform default count) on the device is treated as
  already split and left alone (running-config fallback only).
- Without REST split facts the role cannot tell whether a port can be
  split; the device rejects `split` on such a port and the task fails.
- `channels: 1` (or `0`) is treated as "not split".
- In check mode the split is reported but not pushed (`cli_command` does
  not support check mode for config commands).

## Template generation

With `aoscx_generate_template_config: true`, `templates/int_phys.j2`
writes `split <N>` under the port. Child interfaces get the normal
physical-interface config; they are not treated as dot1q sub-interfaces
even though they have a `parent` in NetBox.
