# AUR packaging

This directory contains the packaging for the `attackshark-battery-bridge` AUR package.

## Files

- `PKGBUILD`
- `.SRCINFO`
- `attackshark-battery-bridge.install`
- `update-srcinfo.sh`

## Release sync

The stable AUR package is updated from GitHub releases.

Relevant automation:

- `.github/workflows/build-release-binary.yml`
- `.github/workflows/sync-aur-release.yml`
- `scripts/render_aur_metadata.py`

Required GitHub Actions secrets:

- `AUR_SSH_PRIVATE_KEY`
- `AUR_MAINTAINER_NAME`
- `AUR_MAINTAINER_EMAIL`

## First submission

For the first push to the AUR repository, use:

```bash
./scripts/init-aur-repo.sh /path/to/aur-keyfile /path/to/local/aur-repo
```

That clones `ssh://aur@aur.archlinux.org/attackshark-battery-bridge.git` with the given key file and copies the initial package files into the repository checkout.

## Manual fallback

If the GitHub Action is not used, render the package metadata manually:

```bash
python scripts/render_aur_metadata.py \
  --version 1.1.0 \
  --source-sha256 <sha256> \
  --output-dir packaging/aur
```

Then update `.SRCINFO` if needed:

```bash
./packaging/aur/update-srcinfo.sh
```
