"""Package the application, documentation, tests and licensed assets."""
import ast
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.6.1"
OUTPUT = ROOT.parent / "output" / f"EzQuote_MVP_v{VERSION}.zip"
PREFIX = "wa_quote_mvp/"
ROOT_FILES = {"run.py", "run_replit.py", ".replit", "requirements.txt", "requirements-dev.txt", "package.json",
              ".gitignore", ".gitattributes", "README.md", "API.md", "LICENSE", "Start Windows.bat",
              "Start Mobile Windows.bat", "Start Mac Linux.command"}
DOCUMENTS = {"USER_GUIDE.md", "DATA_FORMAT.md", "INTEGRATIONS.md", "TESTING.md", "REPLIT.md"}
EXCLUDED_DIRECTORIES = {"data", ".venv", "node_modules", "__pycache__",
                        ".pytest_cache", "test-results"}


def directory_files(directory, suffixes=None):
    """Include nested resources without collecting local runtime outputs."""
    return [path for path in (ROOT / directory).rglob("*")
            if path.is_file()
            and not EXCLUDED_DIRECTORIES.intersection(path.relative_to(ROOT).parts)
            and (suffixes is None or path.suffix.lower() in suffixes)]


def release_files():
    files = [ROOT / name for name in ROOT_FILES]
    files.extend(ROOT / "docs" / name for name in DOCUMENTS)
    files.extend(directory_files("docs/images", {".png", ".svg", ".dot"}))
    files.extend(directory_files("submission", {".md", ".pdf", ".pptx", ".txt", ".mp4"}))
    for directory, suffixes in {"backend": {".py"}, "extension": None,
                                "tests": {".py", ".mjs"}, "assets": {".ttf", ".txt"},
                                "samples": {".xlsx", ".json"}, "mobile": {".html", ".js", ".css"}}.items():
        files.extend(directory_files(directory, suffixes))
    files.append(Path(__file__))
    return sorted(files, key=lambda p: p.relative_to(ROOT).as_posix())


def packaged_bytes(file):
    if file.suffix == ".bat":
        return file.read_text("utf-8").replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")
    return file.read_bytes()


def validate_archive(archive, files):
    assert archive.testzip() is None
    names = archive.namelist()
    expected = {PREFIX + file.relative_to(ROOT).as_posix() for file in files}
    assert len(names) == len(set(names))
    assert set(names) == expected | {PREFIX + "SHA256SUMS.txt"}
    assert not any(EXCLUDED_DIRECTORIES.intersection(Path(name).parts)
                   or name.endswith((".pyc", ".sqlite", ".sqlite3", ".db")) for name in names)

    manifest = json.loads(archive.read(PREFIX + "extension/manifest.json"))
    package = json.loads(archive.read(PREFIX + "package.json"))
    assert manifest["version"] == package["version"] == VERSION
    app_source = ast.parse(archive.read(PREFIX + "backend/app.py"))
    app_versions = [keyword.value.value
                    for node in ast.walk(app_source)
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "FastAPI"
                    for keyword in node.keywords
                    if keyword.arg == "version" and isinstance(keyword.value, ast.Constant)]
    assert app_versions == [VERSION]

    # Verify every packaged source byte, allowing only the established BAT newline normalization.
    for file in files:
        name = PREFIX + file.relative_to(ROOT).as_posix()
        assert archive.read(name) == packaged_bytes(file), name
        mode = archive.getinfo(name).external_attr >> 16
        assert mode == (0o755 if file.suffix == ".command" else 0o644), name

    # The extension must be complete even when it contains new file types or subdirectories.
    extension_names = {PREFIX + file.relative_to(ROOT).as_posix()
                       for file in directory_files("extension")}
    assert {name for name in names if name.startswith(PREFIX + "extension/")} == extension_names
    assert archive.read(PREFIX + "extension/icon128.png").startswith(b"\x89PNG")
    for name in ("LICENSE", "assets/NotoSansSC.ttf", "assets/OFL.txt", "samples/products.json",
                 "samples/business_demo.json", "mobile/index.html", "backend/mobile_gateway.py",
                 "tests/test_previous_eight.py", "tests/test_remaining_edges.py",
                 "tests/test_long_inquiry.py", "tests/test_release_startup.py"):
        assert archive.read(PREFIX + name), name
    for name in ("samples/products.xlsx", "samples/business_demo.xlsx"):
        assert archive.read(PREFIX + name).startswith(b"PK"), name

    checksum_names = set()
    for line in archive.read(PREFIX + "SHA256SUMS.txt").decode("utf-8").splitlines():
        digest, name = line.split("  ", 1)
        assert name not in checksum_names
        checksum_names.add(name)
        assert hashlib.sha256(archive.read(PREFIX + name)).hexdigest() == digest, name
    assert checksum_names == {name.removeprefix(PREFIX) for name in expected}


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    files = release_files()
    for file in files:
        if not file.is_file():
            raise FileNotFoundError(file)
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for file in files:
            data = packaged_bytes(file)
            info = zipfile.ZipInfo(PREFIX + file.relative_to(ROOT).as_posix())
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if file.suffix == ".command" else 0o644) << 16
            archive.writestr(info, data)
        # Hash the packaged bytes, including Windows CRLF normalization.
        hashes = "\n".join(hashlib.sha256(archive.read(name)).hexdigest() + "  " + name.removeprefix(PREFIX) for name in archive.namelist()) + "\n"
        archive.writestr(PREFIX + "SHA256SUMS.txt", hashes.encode("utf-8"))
    with zipfile.ZipFile(OUTPUT) as archive:
        validate_archive(archive, files)
        print(json.dumps({"path": str(OUTPUT), "files": len(archive.namelist()),
                          "bytes": OUTPUT.stat().st_size, "crc": "passed"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
