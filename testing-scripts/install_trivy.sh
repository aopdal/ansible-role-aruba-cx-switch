#!/usr/bin/env bash
# Install trivy for `make audit-repo` (optional; only needed for the repo scan).
#
# Installs the version pinned in .github/workflows/security.yml (TRIVY_VERSION),
# so local scans match CI. The release archive is verified against the
# release's checksums file before anything is installed.
#
# Usage: testing-scripts/install_trivy.sh [install-dir]
#   install-dir  defaults to ~/.local/bin (on PATH in the dev container).
#   TRIVY_VERSION=vX.Y.Z overrides the pinned version.
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd)
install_dir=${1:-$HOME/.local/bin}

version=${TRIVY_VERSION:-$(sed -n 's/^ *TRIVY_VERSION: *"\{0,1\}\(v[0-9.]*\)"\{0,1\} *$/\1/p' \
    "$repo_root/.github/workflows/security.yml")}
if [ -z "$version" ]; then
    echo "Could not read TRIVY_VERSION from .github/workflows/security.yml" >&2
    exit 1
fi
plain=${version#v}

case "$(uname -s)" in
    Linux) os=Linux ;;
    Darwin) os=macOS ;;
    *) echo "Unsupported OS: $(uname -s)" >&2; exit 1 ;;
esac
case "$(uname -m)" in
    x86_64 | amd64) arch=64bit ;;
    aarch64 | arm64) arch=ARM64 ;;
    *) echo "Unsupported architecture: $(uname -m)" >&2; exit 1 ;;
esac

if [ -x "$install_dir/trivy" ] && "$install_dir/trivy" --version 2>/dev/null | grep -q "Version: $plain\$"; then
    echo "trivy $version already installed in $install_dir"
    exit 0
fi

asset="trivy_${plain}_${os}-${arch}.tar.gz"
base="https://github.com/aquasecurity/trivy/releases/download/$version"

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

echo "Downloading $asset ($version)..."
curl -fsSL --proto '=https' -o "$tmp/$asset" "$base/$asset"
curl -fsSL --proto '=https' -o "$tmp/checksums.txt" "$base/trivy_${plain}_checksums.txt"

expected=$(awk -v f="$asset" '$2 == f {print $1}' "$tmp/checksums.txt")
if [ -z "$expected" ]; then
    echo "No checksum for $asset in release checksums" >&2
    exit 1
fi
if command -v sha256sum >/dev/null; then
    actual=$(sha256sum "$tmp/$asset" | awk '{print $1}')
else
    actual=$(shasum -a 256 "$tmp/$asset" | awk '{print $1}')
fi
if [ "$expected" != "$actual" ]; then
    echo "Checksum mismatch for $asset (expected $expected, got $actual)" >&2
    exit 1
fi

tar -xzf "$tmp/$asset" -C "$tmp" trivy
mkdir -p "$install_dir"
install -m 0755 "$tmp/trivy" "$install_dir/trivy"
echo "Installed trivy $version to $install_dir/trivy"
