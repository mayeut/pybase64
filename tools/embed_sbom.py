# /// script
# dependencies = []
# requires-python = ">=3.14"
# ///
import base64
import csv
import dataclasses
import email
import hashlib
import io
import json
import shutil
import string
import subprocess
import sys
import uuid
import zipfile
from pathlib import Path
from typing import Any, Final

ROOT: Final[Path] = Path(__file__).parent.parent.resolve(strict=True)
SBOM_TEMPLATE: Final[str] = """{
  "$schema": "http://cyclonedx.org/schema/bom-1.6.schema.json",
  "bomFormat": "CycloneDX",
  "specVersion": "1.6",
  "serialNumber": "",
  "version": 1,
  "metadata": {
    "component": {
      "bom-ref": "pkg:pypi/{{distribution}}@{{version}}?file_name={{file_name}}",
      "name": "{{distribution}}",
      "purl": "pkg:pypi/{{distribution}}@{{version}}?file_name={{file_name}}",
      "type": "library",
      "version": "{{version}}"
    }
  },
  "components": [
    {
      "bom-ref": "pkg:github/aklomp/base64@{{base64_sha}}",
      "externalReferences": [
        {"type": "license", "url": "https://github.com/aklomp/base64/blob/{{base64_sha}}/LICENSE"},
        {"type": "vcs", "url": "https://github.com/aklomp/base64"}
      ],
      "licenses": [
        {"license": {"id": "BSD-2-Clause", "url": "https://github.com/aklomp/base64/blob/{{base64_sha}}/LICENSE"}}
      ],
      "name": "base64",
      "purl": "pkg:github/aklomp/base64@{{base64_sha}}",
      "type": "library"
    }
  ],
  "dependencies": [
    {
      "ref": "pkg:github/aklomp/base64@{{base64_sha}}"
    },
    {
      "ref": "pkg:pypi/{{distribution}}@{{version}}?file_name={{file_name}}",
      "dependsOn": [
        "pkg:github/aklomp/base64@{{base64_sha}}"
      ]
    }
  ]
}"""


def normalize_label(label: str) -> str:
    chars_to_remove = string.punctuation + string.whitespace
    removal_map = str.maketrans("", "", chars_to_remove)
    return label.translate(removal_map).lower()


def update_sbom(sbom_json: Any, metadata: bytes) -> None:  # noqa: ANN401
    component = sbom_json["metadata"]["component"]
    message = email.message_from_bytes(metadata)
    metadata_version = message["Metadata-Version"]
    major, minor = map(int, metadata_version.split("."))
    if major != 2:
        msg = f"Metadata-Version {metadata_version} not supported"
        raise ValueError(msg)
    if (major, minor) > (2, 5):
        print(f"warning: Metadata-Version {metadata_version} not supported", file=sys.stderr)
    name = message["Name"]
    sbom_name = component["name"]
    if name != sbom_name:
        msg = f"SBOM name {sbom_name!r} does not match METADATA name {name!r}"
        raise ValueError(msg)
    version = message["Version"]
    sbom_version = component["version"]
    if version != sbom_version:
        msg = f"SBOM version {sbom_version!r} does not match METADATA version {version!r}"
        raise ValueError(msg)
    if (major, minor) >= (2, 4) and (license_expr := message.get("License-Expression")):
        component["licenses"] = [{"expression": license_expr}]
    elif license_id := message.get("License"):
        # assume single SPDX id
        component["licenses"] = [{"license": {"id": license_id}}]
    if project_urls := message.get_all("Project-URL"):
        external_references = []
        urls = {}  # used to remove duplicates, only use last seen normalized label
        for project_url in project_urls:
            label, url = project_url.split(",", maxsplit=1)
            type_ = None
            label = normalize_label(label)
            match label:
                case "documentation" | "docs":
                    type_ = "documentation"
                case "homepage":
                    type_ = "website"
                case "issues" | "bugs" | "issue" | "tracker" | "issuetracker" | "bugtracker":
                    type_ = "issue-tracker"
                case "releasenotes":
                    type_ = "release-notes"
                case "source" | "repository" | "sourcecode" | "github":
                    type_ = "vcs"
            if type_ is not None:
                urls[type_] = url.strip()
        for type_, url in urls.items():
            external_references.append({"type": type_, "url": url})
        component["externalReferences"] = external_references
    if summary := message.get("Summary"):
        component["description"] = summary
    if ((author_name := message.get("Author")), (author_email := message.get("Author-Email"))) != (
        None,
        None,
    ):
        author = {}
        if author_name:
            author["name"] = author_name
        if author_email:
            author["email"] = author_email
        component["authors"] = [author]


@dataclasses.dataclass(frozen=True)
class RecordEntry:
    path: str
    hash: str
    size: str


def get_records(record_content: bytes) -> list[RecordEntry]:
    reader = csv.reader(record_content.decode("utf-8").splitlines())
    return [RecordEntry(*row) for row in reader]


def get_record_content(records: list[RecordEntry]) -> bytes:
    with io.StringIO(newline="") as buffer:
        writer = csv.writer(buffer)
        for record in records:
            writer.writerow((record.path, record.hash, record.size))
        return buffer.getvalue().encode("utf-8")


def embed_sbom(sbom_template: str, file: Path, dist_path: Path) -> None:
    distribution, version, _ = file.name.split("-", maxsplit=2)
    sbom_str = sbom_template
    sbom_str = sbom_str.replace("{{distribution}}", distribution)
    sbom_str = sbom_str.replace("{{version}}", version)
    sbom_str = sbom_str.replace("{{file_name}}", file.name)
    sbom_json = json.loads(sbom_str)
    serial_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, sbom_json["metadata"]["component"]["purl"]))
    sbom_json["serialNumber"] = f"urn:uuid:{serial_uuid}"
    dist_info_path = f"{distribution}-{version}.dist-info/"
    metadata_path = f"{dist_info_path}METADATA"
    record_path = f"{dist_info_path}RECORD"
    sboms_path = f"{dist_info_path}sboms/"
    sbom_path = f"{sboms_path}{distribution}.cdx.json"
    overwrite = dist_path in file.parents
    output_file = file.with_suffix(".whl.tmp") if overwrite else dist_path / file.name
    with zipfile.ZipFile(file, "r") as input_zip:
        infos = input_zip.infolist()
        metadata_content = None
        record_info = None
        sboms_info = None
        for info in infos:
            if info.filename == metadata_path:
                metadata_content = input_zip.read(info)
            if info.filename == record_path:
                record_info = info
            elif info.filename == sboms_path:
                sboms_info = info
        if record_info is None:
            msg = f"{record_path!r} not found in {file.name!r}"
            raise ValueError(msg)
        if metadata_content is None:
            msg = f"{metadata_path!r} not found in {file.name!r}"
            raise ValueError(msg)
        records = get_records(input_zip.read(record_info))
        records = [record for record in records if record.path not in {record_path, sbom_path}]
        with zipfile.ZipFile(output_file, "w", compresslevel=9) as output_zip:
            # copy every file except the SBOM (if updated) and RECORD (always updated)
            for info in infos:
                if info.filename not in {record_path, sbom_path}:
                    if info.is_dir():
                        output_zip.mkdir(info)
                    else:
                        output_zip.writestr(info, input_zip.read(info))
            # create sboms dir if needed
            if sboms_info is None:
                sboms_info = zipfile.ZipInfo(sboms_path, date_time=record_info.date_time)
                sboms_info.compress_size = 0
                sboms_info.CRC = 0
                sboms_info.external_attr = ((0o40000 | 0o755) & 0xFFFF) << 16
                sboms_info.file_size = 0
                sboms_info.external_attr |= 0x10
                output_zip.mkdir(sboms_info)
            # embed SBOM
            sbom_info = zipfile.ZipInfo(sbom_path, date_time=record_info.date_time)
            update_sbom(sbom_json, metadata_content)
            sbom_bytes = json.dumps(sbom_json).encode("utf-8")
            output_zip.writestr(sbom_info, sbom_bytes, compress_type=zipfile.ZIP_DEFLATED)
            # update RECORD
            digest = hashlib.sha256(sbom_bytes).digest()
            sha256 = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
            hash_ = f"sha256={sha256}"
            records.append(RecordEntry(sbom_info.filename, hash_, str(len(sbom_bytes))))
            records.append(RecordEntry(record_info.filename, "", ""))
            output_zip.writestr(record_info, get_record_content(records))
    if overwrite:
        file.unlink()
        shutil.move(output_file, file)


def main() -> None:
    has_dist_path = len(sys.argv) >= 2
    has_wheel_path = len(sys.argv) >= 3
    dist_path = Path(sys.argv[1]) if has_dist_path else ROOT / "dist"
    files = [Path(sys.argv[2])] if has_wheel_path else list(dist_path.glob("*.whl"))
    if len(files) == 0:
        print(f"No .whl files found in {dist_path}", file=sys.stderr)
        exit(1)
    base64_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT / "base64",
    ).stdout.strip()
    sbom_template = SBOM_TEMPLATE.replace("{{base64_sha}}", base64_sha)
    for file in files:
        embed_sbom(sbom_template, file, dist_path)


if __name__ == "__main__":
    main()
