#!/usr/bin/env python3
"""Download ripgrep binaries for all supported platforms."""

import hashlib
import os
import platform
import shutil
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

RIPGREP_VERSION = "14.1.1"
VENDOR_DIR = Path(__file__).parent.parent / "vendor" / "ripgrep"

BINARY_CONFIGS = {
    "x64-linux": {
        "url": f"https://github.com/BurntSushi/ripgrep/releases/download/{RIPGREP_VERSION}/ripgrep-{RIPGREP_VERSION}-x86_64-unknown-linux-musl.tar.gz",
        "sha256": "4ef156371199b3ddac1bf584e0e52b1828279af82e4ea864b4a9b816adb0dc1d",
        "extract_path": f"ripgrep-{RIPGREP_VERSION}-x86_64-unknown-linux-musl/rg",
        "binary_name": "rg",
    },
    "arm64-linux": {
        "url": f"https://github.com/BurntSushi/ripgrep/releases/download/{RIPGREP_VERSION}/ripgrep-{RIPGREP_VERSION}-aarch64-unknown-linux-gnu.tar.gz",
        "sha256": "c8c210b99c3ddad9a1a1f9fc7310df5a028c9d95066d449b6abf39c73aa5cf9f",
        "extract_path": f"ripgrep-{RIPGREP_VERSION}-aarch64-unknown-linux-gnu/rg",
        "binary_name": "rg",
    },
    "x64-darwin": {
        "url": f"https://github.com/BurntSushi/ripgrep/releases/download/{RIPGREP_VERSION}/ripgrep-{RIPGREP_VERSION}-x86_64-apple-darwin.tar.gz",
        "sha256": "5c29941af0a9ee28042829af9624829a17ab83dc04a77e3c3c90f56a0f1e0c03",
        "extract_path": f"ripgrep-{RIPGREP_VERSION}-x86_64-apple-darwin/rg",
        "binary_name": "rg",
    },
    "arm64-darwin": {
        "url": f"https://github.com/BurntSushi/ripgrep/releases/download/{RIPGREP_VERSION}/ripgrep-{RIPGREP_VERSION}-aarch64-apple-darwin.tar.gz",
        "sha256": "c055863e7a9ab51f8c3623f5e3e9d8f732d1a85cf1d1fb90e962de6e99b2c5f5",
        "extract_path": f"ripgrep-{RIPGREP_VERSION}-aarch64-apple-darwin/rg",
        "binary_name": "rg",
    },
    "x64-win32": {
        "url": f"https://github.com/BurntSushi/ripgrep/releases/download/{RIPGREP_VERSION}/ripgrep-{RIPGREP_VERSION}-x86_64-pc-windows-msvc.zip",
        "sha256": "43e91ecd1190ba8d904871551f4322e0b4e68fc96e721aad6da13c44cf01045f",
        "extract_path": "rg.exe",
        "binary_name": "rg.exe",
    },
}


def download_file(url: str, dest_path: Path) -> None:
    """Download a file from URL to destination path."""
    print(f"Downloading {url}...")
    with urllib.request.urlopen(url) as response, dest_path.open("wb") as f:  # nosec B310 - URLs are hardcoded GitHub releases
        shutil.copyfileobj(response, f)


def verify_checksum(file_path: Path, expected_sha256: str) -> bool:
    """Verify SHA256 checksum of a file."""
    sha256_hash = hashlib.sha256()
    with file_path.open("rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest() == expected_sha256


def extract_binary(archive_path: Path, extract_path: str, dest_dir: Path, binary_name: str) -> None:
    """Extract binary from archive."""
    if archive_path.suffix == ".zip":
        dest_file = dest_dir / binary_name
        with (
            zipfile.ZipFile(archive_path, "r") as zip_ref,
            zip_ref.open(extract_path) as src,
            dest_file.open("wb") as dst,
        ):
            shutil.copyfileobj(src, dst)
    else:  # tar.gz
        with tarfile.open(archive_path, "r:gz") as tar_ref:
            member = tar_ref.getmember(extract_path)
            member.name = binary_name
            tar_ref.extract(member, dest_dir)

    # Make binary executable on Unix-like systems
    if platform.system() != "Windows":
        binary_path = dest_dir / binary_name
        os.chmod(binary_path, 0o755)


def download_ripgrep_binary(platform_name: str, config: dict) -> None:
    """Download and extract ripgrep binary for a specific platform."""
    platform_dir = VENDOR_DIR / platform_name
    platform_dir.mkdir(parents=True, exist_ok=True)

    binary_path = platform_dir / config["binary_name"]
    if binary_path.exists():
        print(f"Binary already exists: {binary_path}")
        return

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        archive_name = config["url"].split("/")[-1]
        archive_path = temp_path / archive_name

        # Download
        download_file(config["url"], archive_path)

        # Verify checksum
        if not verify_checksum(archive_path, config["sha256"]):
            raise ValueError(f"Checksum verification failed for {platform_name}")

        print(f"Checksum verified for {platform_name}")

        # Extract
        extract_binary(archive_path, config["extract_path"], platform_dir, config["binary_name"])
        print(f"Extracted binary to {binary_path}")


def get_current_platform() -> tuple[str, str]:
    """Get the current platform identifier."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "linux":
        if machine in ["x86_64", "amd64"]:
            return "x64-linux", system
        elif machine in ["aarch64", "arm64"]:
            return "arm64-linux", system
    elif system == "darwin":  # noqa: SIM102
        if machine in ["x86_64", "amd64"]:
            return "x64-darwin", system
        elif machine in ["arm64", "aarch64"]:
            return "arm64-darwin", system
    elif system == "windows":  # noqa: SIM102
        if machine in ["x86_64", "amd64"]:
            return "x64-win32", system

    raise ValueError(f"Unsupported platform: {system} {machine}")


def main():
    """Main function to download ripgrep binaries."""
    import argparse

    parser = argparse.ArgumentParser(description="Download ripgrep binaries")
    parser.add_argument("--all", action="store_true", help="Download for all platforms")
    parser.add_argument("--current", action="store_true", help="Download only for current platform")
    parser.add_argument(
        "--platform", choices=list(BINARY_CONFIGS.keys()), help="Download for specific platform"
    )
    args = parser.parse_args()

    if args.all:
        print("Downloading ripgrep binaries for all platforms...")
        for platform_name, config in BINARY_CONFIGS.items():
            try:
                download_ripgrep_binary(platform_name, config)
            except Exception as e:
                print(f"Error downloading for {platform_name}: {e}")
    elif args.current:
        platform_name, _ = get_current_platform()
        print(f"Downloading ripgrep binary for current platform: {platform_name}")
        download_ripgrep_binary(platform_name, BINARY_CONFIGS[platform_name])
    elif args.platform:
        print(f"Downloading ripgrep binary for {args.platform}")
        download_ripgrep_binary(args.platform, BINARY_CONFIGS[args.platform])
    else:
        # Default to current platform
        platform_name, _ = get_current_platform()
        print(f"Downloading ripgrep binary for current platform: {platform_name}")
        download_ripgrep_binary(platform_name, BINARY_CONFIGS[platform_name])

    print("Done!")


if __name__ == "__main__":
    main()
