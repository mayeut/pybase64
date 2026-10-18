# /// script
# dependencies = ["lastversion>=3.5.0", "requests"]
# requires-python = ">=3.14"
# ///
import hashlib
from pathlib import Path

import requests
from lastversion import latest  # type: ignore[import-not-found]

ROOT = Path(__file__).parent.parent.resolve(strict=True)
VENDOR_DIR = ROOT / "vendor" / "simdutf"


def main() -> None:
    data = latest("simdutf/simdutf", output_format="json")
    tag_name = data["tag_name"]
    license_url_template = "https://raw.githubusercontent.com/simdutf/simdutf/refs/tags/{tag_name}/LICENSE-{licence_kind}"
    for license_kind in ["APACHE", "MIT"]:
        license_url = license_url_template.format(tag_name=tag_name, licence_kind=license_kind)
        request = requests.get(license_url, timeout=30)
        request.raise_for_status()
        VENDOR_DIR.joinpath(f"simdutf-LICENSE-{license_kind}").write_text(
            request.text,
            newline="\n",
        )
    for asset_name in ["simdutf.cpp", "simdutf.h"]:
        asset = next(asset for asset in data["assets_with_digests"] if asset["name"] == asset_name)
        request = requests.get(asset["url"], timeout=30)
        request.raise_for_status()
        asset_data = request.content
        if len(asset_data) != asset["size"]:
            msg = "Invalid asset size. Expected {size}, but got {asset['size']}"
            raise ValueError(msg)
        asset_digest = hashlib.sha256(asset_data).hexdigest()
        if f"sha256:{asset_digest}" != asset["digest"]:
            msg = "Invalid asset digest. Expected {digest}, but got sha256:{asset['digest']}"
            raise ValueError(msg)
        VENDOR_DIR.joinpath(asset_name).write_bytes(asset_data)
    VENDOR_DIR.joinpath("tag").write_text(f"{tag_name}\n")


if __name__ == "__main__":
    main()
