from __future__ import annotations

import argparse
from pathlib import Path


REPO_URL = "https://github.com/maxboeer/attackshark-battery-bridge"
PKGNAME = "attackshark-battery-bridge"
PKGDESC = "Bridge proprietary Attack Shark mouse battery reports into standard Linux battery interfaces"


def render_pkgbuild(version: str, source_sha256: str) -> str:
    return f"""# Maintainer: Max <replace-with-contact@example.com>

pkgname={PKGNAME}
pkgver={version}
pkgrel=1
pkgdesc="{PKGDESC}"
arch=('x86_64')
url="{REPO_URL}"
license=('MIT')
depends=('python' 'systemd')
makedepends=('python-build' 'python-installer' 'python-setuptools' 'python-wheel')
backup=('etc/attackshark-battery-bridge/config.toml')
install="${{pkgname}}.install"
source=("${{pkgname}}-${{pkgver}}.tar.gz::${{url}}/archive/refs/tags/v${{pkgver}}.tar.gz")
sha256sums=('{source_sha256}')

build() {{
  cd "${{srcdir}}/${{pkgname}}-${{pkgver}}"

  python -m build --wheel --no-isolation
}}

package() {{
  cd "${{srcdir}}/${{pkgname}}-${{pkgver}}"

  python -m installer --destdir="${{pkgdir}}" dist/*.whl
  install -Dm644 "packaging/attackshark-battery-bridge.service.pkg" \\
    "${{pkgdir}}/usr/lib/systemd/system/${{pkgname}}.service"
  install -Dm644 "packaging/config.example.toml" \\
    "${{pkgdir}}/etc/attackshark-battery-bridge/config.toml"
  install -Dm644 "README.md" \\
    "${{pkgdir}}/usr/share/doc/${{pkgname}}/README.md"
  install -Dm644 "TECHNICAL.md" \\
    "${{pkgdir}}/usr/share/doc/${{pkgname}}/TECHNICAL.md"
  install -Dm644 "LICENSE.md" \\
    "${{pkgdir}}/usr/share/licenses/${{pkgname}}/LICENSE"
}}
"""


def render_srcinfo(version: str, source_sha256: str) -> str:
    return f"""pkgbase = {PKGNAME}
\tpkgdesc = {PKGDESC}
\tpkgver = {version}
\tpkgrel = 1
\turl = {REPO_URL}
\tinstall = {PKGNAME}.install
\tarch = x86_64
\tlicense = MIT
\tmakedepends = python-build
\tmakedepends = python-installer
\tmakedepends = python-setuptools
\tmakedepends = python-wheel
\tdepends = python
\tdepends = systemd
\tbackup = etc/attackshark-battery-bridge/config.toml
\tsource = {PKGNAME}-{version}.tar.gz::{REPO_URL}/archive/refs/tags/v{version}.tar.gz
\tsha256sums = {source_sha256}

pkgname = {PKGNAME}
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True, help="Release version without leading v")
    parser.add_argument("--source-sha256", required=True, help="sha256 of the release tarball")
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory where PKGBUILD and .SRCINFO should be written",
    )
    args = parser.parse_args()

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "PKGBUILD").write_text(render_pkgbuild(args.version, args.source_sha256), encoding="utf-8")
    (output_dir / ".SRCINFO").write_text(render_srcinfo(args.version, args.source_sha256), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
