# CLAUDE.md

Guidance for Claude Code (and other AI coding assistants) working in this
repository. Read this file before making changes. Keep it short, factual, and
up to date when conventions change.

---

## 1. Project Overview

`aopdal.aruba_cx_switch` is an Ansible role that configures **Aruba AOS-CX
switches** using **NetBox as the single source of truth**. The role owns base
system config, VRFs, VLANs, L2/L3 interfaces, LAG/MCLAG, loopbacks, OSPF, BGP
(via the netbox-bgp plugin), VSX, and EVPN/VXLAN — including idempotent
cleanup of objects no longer present in NetBox.

- Distribution: Ansible Galaxy role (`meta/main.yml`, namespace `aopdal`).
- Required collections: `arubanetworks.aoscx`, `netbox.netbox`,
  `ansible.utils` (see [requirements.yml](requirements.yml)).
- Min Ansible: see `meta/main.yml` (`min_ansible_version`).
- License: MIT.

NetBox is **not optional** — almost every task either reads NetBox config
context / custom fields or transforms NetBox data via filter plugins.

## 2. Repository Layout

```
defaults/main.yml          # All tunables. New variables MUST be declared here.
meta/main.yml              # Galaxy metadata + collection deps.
tasks/                     # Task files. tasks/main.yml is the orchestrator.
templates/                 # Jinja2 templates for `aoscx_config` / generated
                           # starting-point configs (see configure_*.j2).
filter_plugins/            # Custom filters used by tasks/templates.
  netbox_filters.py        # Public filter entry points.
  netbox_filters_lib/      # Implementation modules (vlan, vrf, bgp, ospf,
                           # interface_*, comparison, l3_config_helpers, …).
  rest_api_transforms.py   # REST-API fact transformations.
tests/                     # Ansible test playbooks + tests/unit/ (pytest).
molecule/default/          # Molecule scenario.
docs/                      # User + developer docs (mkdocs source). Index in
                           # docs/index.md (synced from README.md by
                           # `make docs-sync`).
examples/                  # Example playbooks / inventories.
testing-scripts/           # Helper scripts for local testing.
Makefile                   # Canonical entry point for lint / test / docs.
```

The companion workspace folder `aruba-role-testing/` (sibling repo) holds the
real-device test environment (NetBox bootstrap playbooks, group vars, ZTP
configs, firmware). It is **not** part of this role and must not be modified
when working on role changes unless explicitly asked.

## 3. Task Orchestration (tasks/main.yml)

Order matters and is encoded in `tasks/main.yml`. Do not reorder casually.

1. Fact gathering (`gather_facts.yml`, optionally `gather_facts_rest_api.yml`
   when `aoscx_gather_facts_rest_api: true`).
2. Optional template-based config generation
   (`aoscx_generate_template_config`).
3. Base system (no VRF dependency): banner → timezone → anycast gateway.
4. **VRFs** — must precede anything that can reference a VRF (L3 interfaces,
   NTP, DNS, OSPF, BGP).
5. VRF-dependent base services: NTP → DNS (both can be bound to a VRF, so
   the VRF must exist first).
6. **VLAN change identification** (`identify_vlan_changes.yml`) — sets
   `vlans`, `vlans_in_use`, `vlan_changes`. Required by all VLAN/EVPN/VXLAN
   tasks.
7. VLAN configuration.
8. **Interface change identification** (`identify_interface_changes.yml`) —
   sets `interface_changes` (categorised: physical / lag / mclag / l2 / l3 /
   no_changes). Required by all interface tasks.
9. Interfaces: physical → LAG → MCLAG → assign-to-LAG → L2 → OSPF → L3.
10. EVPN, VXLAN.
11. **Idempotent cleanup** (only when `aoscx_idempotent_mode: true`):
    re-gather facts → re-identify VLAN changes → cleanup EVPN → VXLAN →
    VLANs.
12. BGP, VSX.
13. `aoscx_config: save_when: modified` if `aoscx_save_config`.

### Feature-dependency ordering rule

When adding or moving a feature in `tasks/main.yml`, **verify its
dependencies and place it after every prerequisite**. A feature `B` depends
on feature `A` if any of the following is true:

- `B` references an object that `A` creates (e.g. NTP/DNS bound to a VRF;
  L3 interface attached to a VRF; SVI/anycast under a VLAN; BGP using a
  loopback as router-id; EVPN referencing a VLAN; VXLAN referencing a VLAN
  and a loopback source).
- `B` reads facts that only become accurate after `A` has run (e.g. cleanup
  steps that re-gather facts after configuration).
- `B`'s change-detection task (`identify_*_changes.yml`) depends on data
  produced by `A`.

Existing dependency chains to preserve:

| Feature           | Depends on                                                  |
| ----------------- | ----------------------------------------------------------- |
| NTP, DNS          | VRFs                                                        |
| L3 interfaces     | VRFs, physical/LAG interfaces                               |
| SVIs / anycast    | VLANs                                                       |
| LAG member assign | LAG / MCLAG creation, physical interfaces                   |
| OSPF, BGP         | VRFs, L3 interfaces (loopbacks for router-id / peering)     |
| EVPN              | VLANs                                                       |
| VXLAN             | VLANs, loopback (source-interface)                          |
| VSX               | MCLAG, ISL/keepalive interfaces                             |
| Cleanup tasks     | Re-gathered facts AFTER all configuration tasks             |
| `save_when`       | Last (after every change)                                   |

If a new feature has no dependencies, place it in the base-system block.
Otherwise document the dependency in a comment above the include and
update the table above in the same change.

Many tasks also gate on **NetBox custom fields** on the device:
`device_ospf`, `device_bgp`, `device_vsx`, `device_evpn`, `device_vxlan`,
`device_anycast_gateway`. Respect these gates when adding new features.

## 4. Conventions (READ BEFORE EDITING)

These are the project's hard rules. Follow them or the change will be
rejected by lint / review.

### 4.1 Variables

- **Every new variable MUST be declared in
  [defaults/main.yml](defaults/main.yml)** with a short comment explaining
  intent, valid values, and any version requirement. Do not introduce
  undeclared variables via `default(...)` only — declare the default in
  `defaults/main.yml` so users can discover and override it.
- Variable names are prefixed `aoscx_` (role-owned) or read from NetBox as
  `custom_fields.device_*` / `interfaces` / `vlans` etc.
- Booleans are filtered with `| bool` at the use site.
- Do not rename or remove existing variables without a deprecation entry
  (see `aoscx_fast_mode` for the pattern: keep the variable, add a debug
  warning in `tasks/main.yml`, document in `CHANGELOG.md`).

### 4.2 Tasks

- Use **FQCN** for all modules (`ansible.builtin.*`, `arubanetworks.aoscx.*`,
  `netbox.netbox.*`). Enforced by ansible-lint (`fqcn`).
- Task names use sentence case and start with a verb; ansible-lint
  `name[prefix]` is enabled.
- Prefer `ansible.builtin.include_tasks` with `apply: tags:` over `import_*`
  so tags propagate to dynamically included tasks (this is the established
  pattern in `tasks/main.yml`).
- Always tag includes with both a feature tag and a layer tag
  (e.g. `vlans` + `layer2`, `bgp` + `routing` + `layer3`). The full tag
  taxonomy is documented in [docs/TAG_DEPENDENT_INCLUDES.md](docs/TAG_DEPENDENT_INCLUDES.md).
- Keep tasks **idempotent**. Where the upstream module is not idempotent
  (notably `aoscx_config` for L3), pre-compare against gathered facts and
  only act on the diff — see `tasks/configure_l3_interface_common.yml` and
  the helpers in
  [filter_plugins/netbox_filters_lib/l3_config_helpers.py](filter_plugins/netbox_filters_lib/l3_config_helpers.py).
- L3 interfaces use `aoscx_config` (not `aoscx_l3_interface`) so that
  `ip mtu` and `l3-counters` can be set. Do not "simplify" back to
  `aoscx_l3_interface` — capability would regress.

### 4.3 Filter plugins

- New filters go in `filter_plugins/netbox_filters_lib/<topic>.py` and are
  re-exported from `filter_plugins/netbox_filters.py`.
- Every public filter needs a unit test under `tests/unit/`. Run with
  `make test-unit` or `make test-unit-coverage`.
- Filters must be pure functions of their inputs (no I/O, no global state).

### 4.4 Templates

- Jinja2 templates under `templates/` use 2-space indentation and target
  AOS-CX CLI syntax. They are consumed by `aoscx_config` or written as
  starting-point configs when `aoscx_generate_template_config: true`.

### 4.5 Documentation

When you change behaviour, **also update `docs/`**. The site is built with
MkDocs from `mkdocs.yml`; `docs/index.md` is regenerated from `README.md` by
`make docs-sync`, so README-level changes propagate automatically — but
topic docs do not.

Update the relevant topic page when you touch its area:

| Area touched                                  | Doc to update                                                                                |
| --------------------------------------------- | -------------------------------------------------------------------------------------------- |
| Any new/changed variable in `defaults/main.yml` | [README.md](README.md) "Role Variables" + the topic doc for that feature                   |
| VLANs / VLAN cleanup                          | [docs/VLAN_CHANGE_IDENTIFICATION_WORKFLOW.md](docs/VLAN_CHANGE_IDENTIFICATION_WORKFLOW.md), [docs/VLAN_DEVELOPER_GUIDE.md](docs/VLAN_DEVELOPER_GUIDE.md) |
| L2 interfaces                                 | [docs/L2_INTERFACE_MODES.md](docs/L2_INTERFACE_MODES.md)                                     |
| L3 / anycast / loopback                       | [docs/ANYCAST_GATEWAY.md](docs/ANYCAST_GATEWAY.md)                                           |
| BGP                                           | [docs/BGP_CONFIGURATION.md](docs/BGP_CONFIGURATION.md)                                       |
| OSPF                                          | [docs/OSPF_CONFIGURATION.md](docs/OSPF_CONFIGURATION.md)                                     |
| EVPN / VXLAN                                  | [docs/EVPN_VXLAN_CONFIGURATION.md](docs/EVPN_VXLAN_CONFIGURATION.md)                         |
| DNS / NTP / banner / timezone                 | [docs/BASE_CONFIGURATION.md](docs/BASE_CONFIGURATION.md), [docs/DNS_CONFIGURATION.md](docs/DNS_CONFIGURATION.md) |
| Filter plugins                                | [docs/FILTER_PLUGINS.md](docs/FILTER_PLUGINS.md), [docs/FILTER_PLUGINS_REUSE.md](docs/FILTER_PLUGINS_REUSE.md) |
| NetBox custom fields / config context         | [docs/NETBOX_INTEGRATION.md](docs/NETBOX_INTEGRATION.md)                                     |
| Tag-driven inclusion / new tag                | [docs/TAG_DEPENDENT_INCLUDES.md](docs/TAG_DEPENDENT_INCLUDES.md), [docs/TESTING.md](docs/TESTING.md) (Tag-Dependent Task Testing section) |
| Performance / fact gathering                  | [docs/PERFORMANCE_OPTIMIZATION.md](docs/PERFORMANCE_OPTIMIZATION.md), [docs/ANSIBLE_CACHE_DIRECTORY.md](docs/ANSIBLE_CACHE_DIRECTORY.md) |
| Templates                                     | [docs/TEMPLATE_CONFIGURATION.md](docs/TEMPLATE_CONFIGURATION.md)                             |
| Testing infra                                 | [docs/TESTING.md](docs/TESTING.md) (single consolidated guide — includes unit tests, lab setup, scripts, tag tests) |
| Releases                                      | [CHANGELOG.md](CHANGELOG.md), [docs/RELEASE_PROCESS.md](docs/RELEASE_PROCESS.md)             |

If a feature has no existing doc, add a new page under `docs/` and link it
from [docs/README_DOCS.md](docs/README_DOCS.md) and (where appropriate)
`mkdocs.yml` nav.

Documentation style: Markdown, sentence-case headings, ATX (`#`) syntax,
relative links to other docs, fenced code blocks with language hints. Do not
use emojis in headings.

### 4.6 Changelog

User-visible changes go in [CHANGELOG.md](CHANGELOG.md) under an
`Unreleased` section using Keep-a-Changelog headings (`Added`, `Changed`,
`Deprecated`, `Removed`, `Fixed`, `Security`).

## 5. Common Commands

All canonical commands live in the [Makefile](Makefile). Run `make help` for
the auto-generated list. Most targets depend on the venv created by
`make venv` / `make setup` and activate it via `. .venv/bin/activate`.

### Setup & environment

| Target              | Purpose                                                              |
| ------------------- | -------------------------------------------------------------------- |
| `make help`         | Show all targets (default goal).                                     |
| `make venv`         | Create `.venv/` if missing.                                          |
| `make install`      | Install `requirements-test.txt` + Galaxy collections into the venv.  |
| `make pre-commit-setup` | Install pre-commit git hooks.                                    |
| `make setup`        | `install` + `pre-commit-setup` (one-shot bootstrap).                 |
| `make info`         | Print Python / Ansible / Molecule / Docker / dev-container status.   |

### Lint & static checks

| Target              | Purpose                                                              |
| ------------------- | -------------------------------------------------------------------- |
| `make yamllint`     | YAML lint via `.yamllint`.                                           |
| `make ansible-lint` | Ansible lint via `.ansible-lint` (production profile, mocked aoscx). |
| `make lint`         | `yamllint` + `ansible-lint`.                                         |
| `make syntax`       | `ansible-playbook tests/test.yml --syntax-check`.                    |
| `make pre-commit`   | Run all pre-commit hooks across the repo.                            |

### Tests

| Target                     | Purpose                                                       |
| -------------------------- | ------------------------------------------------------------- |
| `make test-unit`           | Pytest filter unit tests under `tests/unit/`.                 |
| `make test-unit-quick`     | Same, no coverage, short tracebacks.                          |
| `make test-unit-coverage`  | Unit tests + HTML coverage in `htmlcov/`.                     |
| `make integration`         | Run `tests/test.yml` against `tests/inventory` (needs target). |
| `make test-quick`          | `lint` + `syntax` (fast PR gate).                             |
| `make test`                | `lint` + `syntax` + `molecule-test` (full).                   |
| `make all`                 | `clean` + `setup` + `test`.                                   |

### Molecule

| Target                   | Purpose                                       |
| ------------------------ | --------------------------------------------- |
| `make molecule-create`   | Create the molecule instance.                 |
| `make molecule-converge` | Converge only (re-run role).                  |
| `make molecule-verify`   | Run verifier.                                 |
| `make molecule-test`     | Full molecule lifecycle.                      |
| `make molecule-destroy`  | Tear down the instance.                       |

### Docs

| Target              | Purpose                                                              |
| ------------------- | -------------------------------------------------------------------- |
| `make docs-install` | Install `requirements-docs.txt` (mkdocs + plugins).                  |
| `make docs-sync`    | Copy `README.md` → `docs/index.md` and `CHANGELOG.md` → `docs/CHANGELOG.md`, rewriting internal links. Run this whenever README/CHANGELOG change. |
| `make docs-serve`   | Live preview at <http://127.0.0.1:8000>.                             |
| `make docs-build`   | Build static site into `site/`.                                      |
| `make docs`         | Alias for `docs-serve`.                                              |

### Housekeeping

| Target           | Purpose                                                                  |
| ---------------- | ------------------------------------------------------------------------ |
| `make clean`     | Remove `.cache`, `.pytest_cache`, `.molecule`, `tests/output`, `__pycache__`, `*.pyc`, `*.retry`; destroy molecule instance if present. |
| `make clean-all` | `clean` + remove `.venv/`.                                               |
| `make watch`     | Re-run `make lint` on YAML changes (requires `entr`).                    |

**Minimum gate before opening a PR:**
`make lint && make test-unit && make syntax` (and `make docs-sync` if you
touched `README.md` or `CHANGELOG.md`).

## 6. Testing Notes

- Unit tests live in `tests/unit/` and use pytest. They are the fastest
  feedback loop for filter changes.
- Integration playbooks under `tests/` (`test.yml`, `test_base_config.yml`,
  `test_dns_config.yml`, `test_lag_order.yml`, `test_real_data.yml`,
  `test_tags.yml`) require a real or simulated AOS-CX target and the
  sibling `aruba-role-testing` workspace.
- Molecule scenario: `molecule/default/` — driven via `make molecule-*`.
- `ansible-lint` is configured to `production` profile in
  [`.ansible-lint`](.ansible-lint) with mocks for all `aoscx_*` modules so
  lint runs without the collection installed in the lint env.

## 7. AI Assistant Working Rules

When acting on this repo:

1. **Discover before editing.** Read `tasks/main.yml`, the relevant
   `tasks/configure_*.yml`, and the matching `docs/` page first.
2. **Declare variables in `defaults/main.yml`.** Never silently introduce
   a variable through `default(...)` only.
3. **Use FQCN** and the established `include_tasks + apply: tags` pattern.
4. **Preserve idempotency.** If you must call a non-idempotent module,
   pre-compare with gathered facts (see L3 helpers).
5. **Update `docs/`** in the same change as code — see the table in §4.5.
6. **Update `CHANGELOG.md`** for any user-visible change.
7. **Add unit tests** for any new or changed filter in
   `filter_plugins/netbox_filters_lib/`.
8. **Don't reorder `tasks/main.yml`** without an explicit reason; ordering
   is load-bearing (VRFs before L3, VLAN identify before VLAN config,
   cleanup last, save last).
9. **Don't touch `aruba-role-testing/`** when fixing the role unless the
   user asks.
10. **Run `make lint` and `make test-unit`** before declaring the task
    done.

## 8. Pointers

- Top-level overview: [README.md](README.md)
- Doc index: [docs/README_DOCS.md](docs/README_DOCS.md)
- Quick start: [docs/QUICKSTART.md](docs/QUICKSTART.md)
- Developer guide: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)
- Contributing: [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)
- NetBox integration: [docs/NETBOX_INTEGRATION.md](docs/NETBOX_INTEGRATION.md)
- Filters reference: [docs/FILTER_PLUGINS.md](docs/FILTER_PLUGINS.md)
- Tag taxonomy: [docs/TAG_DEPENDENT_INCLUDES.md](docs/TAG_DEPENDENT_INCLUDES.md)
- Release process: [docs/RELEASE_PROCESS.md](docs/RELEASE_PROCESS.md)
