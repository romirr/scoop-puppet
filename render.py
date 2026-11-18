#!/usr/bin/env python3
"""render package-manager manifests for a puppet release from its SHA256SUMS.

usage: render.py <formula|scoop|winget> <tag> <SHA256SUMS file or url> <out>

  formula  -> <out> is a file   (homebrew formula)
  scoop    -> <out> is a file   (scoop manifest)
  winget   -> <out> is a folder (version, installer and locale manifests)

stdlib only. the same script is copied into the homebrew-puppet and scoop-puppet repos, whose
update workflows run it against the latest release.
"""
import datetime
import json
import os
import pathlib
import sys
import urllib.request

REPO = "romirr/puppet"
HOME = f"https://github.com/{REPO}"
DESC = "puppet (browser) control: agents drive your real chrome through a small extension and a rust binary"
TARGETS = {
    "mac_arm": ("aarch64-apple-darwin", "tar.gz"),
    "mac_x64": ("x86_64-apple-darwin", "tar.gz"),
    "linux_arm": ("aarch64-unknown-linux-gnu", "tar.gz"),
    "linux_x64": ("x86_64-unknown-linux-gnu", "tar.gz"),
    "win_x64": ("x86_64-pc-windows-msvc", "zip"),
    "win_arm": ("aarch64-pc-windows-msvc", "zip"),
}


def read(src):
    if src.startswith("http"):
        with urllib.request.urlopen(src) as r:
            return r.read().decode()
    return pathlib.Path(src).read_text()


def sums(text):
    out = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2:
            out[parts[1].lstrip("*")] = parts[0]
    return out


def asset(tag, key):
    triple, ext = TARGETS[key]
    return f"puppet-{triple}.{ext}", f"{HOME}/releases/download/{tag}/puppet-{triple}.{ext}"


def info(tag, s):
    res = {}
    for key in TARGETS:
        name, url = asset(tag, key)
        if name not in s:
            sys.exit(f"{name} is not in SHA256SUMS")
        res[key] = (url, s[name])
    return res


def formula(tag, s):
    v = tag.lstrip("v")
    a = info(tag, s)

    def block(os_, arch_, key):
        url, h = a[key]
        return (
            f"    on_{arch_} do\n"
            f'      url "{url}"\n'
            f'      sha256 "{h}"\n'
            f"    end\n"
        )

    return f'''class Puppet < Formula
  desc "{DESC}"
  homepage "{HOME}"
  version "{v}"
  license "Apache-2.0"

  on_macos do
{block("macos", "arm", "mac_arm")}{block("macos", "intel", "mac_x64")}  end

  on_linux do
{block("linux", "arm", "linux_arm")}{block("linux", "intel", "linux_x64")}  end

  def install
    bin.install "puppet"
  end

  def caveats
    <<~EOS
      puppet needs a browser extension and a native host registration, once:
        puppet install
      then in chrome: chrome://extensions, developer mode, load unpacked (the folder puppet install prints).
      check with:
        puppet doctor
      mcp clients: puppet mcp --config <client>
    EOS
  end

  test do
    assert_match "puppet #{{version}}", shell_output("#{{bin}}/puppet --version")
  end
end
'''


def scoop(tag, s):
    v = tag.lstrip("v")
    a = info(tag, s)
    base = f"{HOME}/releases/download/v$version"
    m = {
        "version": v,
        "description": DESC,
        "homepage": HOME,
        "license": "Apache-2.0",
        "architecture": {
            "64bit": {"url": a["win_x64"][0], "hash": a["win_x64"][1]},
            "arm64": {"url": a["win_arm"][0], "hash": a["win_arm"][1]},
        },
        "bin": "puppet.exe",
        "notes": [
            "puppet needs a browser extension and a native host registration, once:",
            "  puppet install",
            "then in chrome: chrome://extensions, developer mode, load unpacked (the folder puppet install prints). check with: puppet doctor",
        ],
        "checkver": "github",
        "autoupdate": {
            "architecture": {
                "64bit": {"url": f"{base}/puppet-x86_64-pc-windows-msvc.zip"},
                "arm64": {"url": f"{base}/puppet-aarch64-pc-windows-msvc.zip"},
            },
            "hash": {"url": f"{base}/SHA256SUMS", "regex": "$sha256\\s+$basename"},
        },
    }
    return json.dumps(m, indent=4) + "\n"


def winget(tag, s, out):
    v = tag.lstrip("v")
    a = info(tag, s)
    pid = "romirr.puppet"
    schema = "https://aka.ms/winget-manifest.{}.1.6.0.schema.json"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{pid}.yaml").write_text(
        f"# yaml-language-server: $schema={schema.format('version')}\n"
        f"PackageIdentifier: {pid}\nPackageVersion: {v}\nDefaultLocale: en-US\n"
        f"ManifestType: version\nManifestVersion: 1.6.0\n"
    )
    inst = "".join(
        f"  - Architecture: {arch}\n    InstallerUrl: {a[key][0]}\n    InstallerSha256: {a[key][1].upper()}\n"
        for arch, key in (("x64", "win_x64"), ("arm64", "win_arm"))
    )
    (out / f"{pid}.installer.yaml").write_text(
        f"# yaml-language-server: $schema={schema.format('installer')}\n"
        f"PackageIdentifier: {pid}\nPackageVersion: {v}\nMinimumOSVersion: 10.0.17763.0\n"
        f"InstallerType: zip\nNestedInstallerType: portable\nNestedInstallerFiles:\n"
        f"  - RelativeFilePath: puppet.exe\n    PortableCommandAlias: puppet\n"
        f"Commands:\n  - puppet\nInstallModes:\n  - silent\n  - silentWithProgress\n"
        f"ReleaseDate: {os.environ.get('PUPPET_RELEASE_DATE') or datetime.date.today().isoformat()}\nInstallers:\n{inst}"
        f"ManifestType: installer\nManifestVersion: 1.6.0\n"
    )
    (out / f"{pid}.locale.en-US.yaml").write_text(
        f"# yaml-language-server: $schema={schema.format('defaultLocale')}\n"
        f"PackageIdentifier: {pid}\nPackageVersion: {v}\nPackageLocale: en-US\n"
        f"Publisher: romirr\nPublisherUrl: https://github.com/romirr\nPublisherSupportUrl: {HOME}/issues\n"
        f"PackageName: puppet\nPackageUrl: {HOME}\nLicense: Apache-2.0\nLicenseUrl: {HOME}/blob/main/LICENSE\n"
        f"ShortDescription: {json.dumps(DESC)}\n"
        f"Description: >-\n  puppet lets AI agents drive your real, signed-in chrome through a small MV3 extension and a rust\n"
        f"  native host. no remote-debugging prompt, no open port, no headless twin. one binary: cli and mcp server.\n"
        f"Moniker: puppet\nTags:\n  - browser\n  - automation\n  - mcp\n  - chrome\n  - agents\n"
        f"ReleaseNotesUrl: {HOME}/releases/tag/{tag}\n"
        f"ManifestType: defaultLocale\nManifestVersion: 1.6.0\n"
    )


def main():
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    kind, tag, src, out = sys.argv[1:]
    s = sums(read(src))
    if kind == "formula":
        pathlib.Path(out).write_text(formula(tag, s))
    elif kind == "scoop":
        pathlib.Path(out).write_text(scoop(tag, s))
    elif kind == "winget":
        winget(tag, s, pathlib.Path(out))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
