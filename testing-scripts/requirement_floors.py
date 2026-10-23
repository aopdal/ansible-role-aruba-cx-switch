#!/usr/bin/env python3
"""
Print the lowest allowed version of every direct requirement

Turns each ">=X" lower bound in the given requirements files into "name==X",
so pip-audit can check the oldest versions a user is still allowed to install:

    python testing-scripts/requirement_floors.py requirements.txt > floors.txt
    pip-audit --no-deps --disable-pip -r floors.txt

pip-audit cannot see a version that was never released and reports it clean,
so pass --verify to confirm every floor exists on PyPI (needs network).

Requirements without a ">=" lower bound are reported on stderr and make the
script exit non-zero: an open-ended requirement allows arbitrarily old (and
vulnerable) releases.
"""

import json
import re
import sys
import urllib.error
import urllib.request

from packaging.version import Version

REQUIREMENT = re.compile(r"^(?P<name>[A-Za-z0-9._-]+)(?:\[[^\]]*\])?\s*(?P<spec>.*)$")
LOWER_BOUND = re.compile(r">=\s*(?P<version>[^,;\s]+)")


def floors(lines):
    """Yield (name, floor_version_or_None) for each requirement line"""
    for raw in lines:
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        match = REQUIREMENT.match(line)
        if not match:
            continue
        bound = LOWER_BOUND.search(match.group("spec"))
        yield match.group("name"), bound.group("version") if bound else None


def released(name, version):
    """Return True if name==version exists on PyPI"""
    url = f"https://pypi.org/pypi/{name}/{version}/json"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return json.load(response)["info"]["version"] is not None
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return False
        raise


def main(paths, verify=False):
    """Print name==floor for every requirement in paths"""
    seen = {}
    missing = []
    for path in paths:
        with open(path, encoding="utf-8") as handle:
            for name, version in floors(handle):
                if version is None:
                    missing.append(f"{path}: {name}")
                    continue
                key = name.lower().replace("_", "-")
                # When files disagree, the highest floor is the effective one
                if key not in seen or Version(version) > Version(seen[key][1]):
                    seen[key] = (name, version)
    for name, version in seen.values():
        print(f"{name}=={version}")
    for entry in missing:
        print(f"no '>=' lower bound: {entry}", file=sys.stderr)
    unreleased = [
        f"{name}=={version}"
        for name, version in seen.values()
        if verify and not released(name, version)
    ]
    for entry in unreleased:
        print(f"floor is not a released version: {entry}", file=sys.stderr)
    return 1 if missing or unreleased else 0


if __name__ == "__main__":
    args = sys.argv[1:]
    check = "--verify" in args
    files = [arg for arg in args if arg != "--verify"]
    if not files:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    sys.exit(main(files, verify=check))
