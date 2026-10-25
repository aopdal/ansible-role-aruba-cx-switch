# Security and dependency checks

This role is distributed as source. It does not ship or pin the Python
packages, Ansible collections or container images it runs with: it declares
**minimum versions**, and you install whatever is current in your own
environment. This page explains what the project checks and what remains
your responsibility.

## What the project guarantees

| Area | Check | Where |
| ---- | ----- | ----- |
| Python dependencies, latest | The newest versions `requirements.txt` and `requirements-test.txt` allow have no known vulnerabilities (`pip-audit`, PyPI advisory database). This covers `ansible-core`. | `make audit`, Security workflow |
| Python dependencies, minimum | Every declared `>=` minimum is a released version with no known vulnerabilities, so an older environment that still satisfies the requirements is not knowingly vulnerable. | `make audit`, Security workflow |
| Repository | No misconfigurations or committed secrets (`trivy fs`). | `make audit-repo`, Security workflow |
| Devcontainer | The image built from `.devcontainer/Dockerfile` is scanned for fixable HIGH/CRITICAL CVEs (informational). It is based on the official `python:3.12-slim` image and upgrades Debian packages and pip, so a rebuild picks up current fixes. | Security workflow |
| GitHub Actions, devcontainer features | Kept up to date by Dependabot. | `.github/dependabot.yml` |

The [Security workflow](https://github.com/aopdal/ansible-role-aruba-cx-switch/actions/workflows/security.yml)
runs on every pull request, on pushes to `main`, and weekly — new CVEs are
published against dependencies that have not changed, so a check that passed
last month can fail today.

### Ansible collections

`arubanetworks.aoscx`, `netbox.netbox` and the other collections in
`requirements.yml` are not covered by any vulnerability database that a
scanner can query. The project:

- installs the latest collection versions in every CI run, so unit tests and
  Molecule catch breaking changes early;
- follows releases and security advisories of the upstream collection
  repositories, and raises the minimums in `requirements.yml` when a
  security fix is published.

## What you are responsible for

Your control node, virtual environment and containers are yours to keep up to
date. A clean result from this project does not mean your installed versions
are clean: they are whatever you installed, whenever you installed them.

### Check your Python environment

Run `pip-audit` inside the environment you run the role from:

```bash
pip install pip-audit
pip-audit
```

Or scan a virtual environment from outside with trivy. Use `rootfs`, not
`fs`: `trivy fs` reads lockfiles only and finds nothing in a venv.

```bash
trivy rootfs --scanners vuln .venv
```

Findings reported under `pip/_vendor` are copies of libraries bundled inside
pip itself. They are fixed by upgrading pip (`pip install -U pip`) once a pip
release ships newer copies, not by upgrading the libraries separately.

### Upgrade

```bash
pip install -U -r requirements.txt
ansible-galaxy collection install -U -r requirements.yml
```

`ansible-core` is capped below 2.20 because `arubanetworks.aoscx` 4.5.1 does
not support newer cores; upgrades stay within the 2.19 series.

## For maintainers

- Run `make audit` after changing any `requirements*.txt` file. It audits the
  latest allowed versions, then the declared minimums via
  [`testing-scripts/requirement_floors.py`](../testing-scripts/requirement_floors.py),
  which turns each `>=X` into `==X` and, with `--verify`, fails on a minimum
  that was never released (`pip-audit` reports unreleased versions as clean).
- Every Python requirement needs a `>=` lower bound; the floor check fails on
  open-ended requirements, because they allow arbitrarily old releases.
- When the minimum-version audit fails, raise the floor to the first fixed
  version and record it under `Security` in `CHANGELOG.md`. If an advisory
  has no fixed version, raise the floor past the affected range (see
  `paramiko` in `requirements.txt`).
- `make audit-repo` runs the same trivy scan as CI and needs trivy installed
  locally. trivy is optional for local work; `make install-trivy` installs
  the CI-pinned version to `~/.local/bin` (also in the dev container) via
  [`testing-scripts/install_trivy.sh`](../testing-scripts/install_trivy.sh),
  after verifying the release checksum. Suppressions live in [`.trivyignore`](../.trivyignore), each with
  a justification.
