import importlib.metadata
import json

import pytest

import pybase64


def test_name() -> None:
    metadata = importlib.metadata.metadata("pybase64")
    assert metadata["Name"] == "pybase64"


def test_version() -> None:
    metadata = importlib.metadata.metadata("pybase64")
    assert metadata["Version"] == pybase64.__version__


def test_license() -> None:
    metadata = importlib.metadata.metadata("pybase64")
    assert metadata["License-Expression"] == "BSD-2-Clause"


@pytest.mark.pypi_distribution
def test_sbom() -> None:  # pragma: no cover
    metadata = importlib.metadata.metadata("pybase64")
    distribution = metadata["Name"]
    version = metadata["Version"]
    license_ = metadata["License-Expression"]
    files = importlib.metadata.files("pybase64")
    assert files is not None
    sbom_name = f"{distribution}.cdx.json"
    sboms = [file for file in files if file.name == sbom_name]
    assert len(sboms) == 1
    sbom = sboms[0]
    assert sbom.parent.name == "sboms"
    assert sbom.parent.parent.name == f"{distribution}-{version}.dist-info"
    sbom_data = json.loads(sbom.read_text())
    purl_prefix = f"pkg:pypi/{distribution}@{version}?file_name={distribution}-{version}-"
    sbom_purl = sbom_data["metadata"]["component"]["purl"]
    sbom_bom_ref = sbom_data["metadata"]["component"]["bom-ref"]
    sbom_version = sbom_data["metadata"]["component"]["version"]
    sbom_licenses = sbom_data["metadata"]["component"]["licenses"]
    assert len(sbom_licenses) == 1
    sbom_license = sbom_licenses[0]["expression"]
    assert sbom_purl.startswith(purl_prefix)
    assert sbom_bom_ref == sbom_purl
    assert sbom_version == version
    assert sbom_license == license_
