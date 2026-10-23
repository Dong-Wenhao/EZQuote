"""Package only deliverable source, synthetic sample data and licensed assets."""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT.parent / "output" / "EzQuote_MVP_v1.6.1.zip"
ROOT_FILES = {"run.py", "requirements.txt", "requirements-dev.txt", "package.json",
              ".gitignore", "README_先读我.md", "先看这里.txt", "API.md", "VERIFICATION.md",
              "Start Windows.bat", "Start Mobile Windows.bat", "Start Mac Linux.command",
              "更新到1.5_先看这里.md", "经营数据模板说明.md", "功能覆盖说明_1.5.md",
              "队友使用指南_1.6.docx", "1.5_修复与测试对照.md", "1.5_自查修订说明.md", "1.5.2_复测修复说明.md", "1.5.3_自查与修复说明.md", "1.5.4_优化与验收说明.md", "1.6_界面更新说明.md", "1.6.1_最终交付检查.md", "接入AI与手机通知_1.2.md"}


def release_files():
    files = [ROOT / name for name in ROOT_FILES]
    for directory, suffixes in {"backend": {".py"}, "extension": {".json", ".js", ".html", ".css", ".png"},
                                "tests": {".py", ".mjs"}, "assets": {".ttf", ".txt"},
                                "samples": {".xlsx", ".json"}, "mobile": {".html", ".js", ".css"},
                                "docs": {".docx"}, "qa-results": {".json", ".txt"},
                                "independent-results": {".py"}, "retest-results": {".py"}}.items():
        files.extend(p for p in (ROOT / directory).iterdir() if p.is_file() and p.suffix in suffixes)
    files.append(ROOT / "tools" / "build_business_sample.mjs")
    files.append(Path(__file__))
    return sorted(files, key=lambda p: p.relative_to(ROOT).as_posix())


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    files = release_files()
    for file in files:
        if not file.is_file():
            raise FileNotFoundError(file)
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for file in files:
            data = file.read_bytes()
            if file.suffix == ".bat":
                data = file.read_text("utf-8").replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")
            info = zipfile.ZipInfo("wa_quote_mvp/" + file.relative_to(ROOT).as_posix())
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if file.suffix == ".command" else 0o644) << 16
            archive.writestr(info, data)
        # Hash the packaged bytes, including Windows CRLF normalization.
        hashes = "\n".join(hashlib.sha256(archive.read(name)).hexdigest() + "  " + name.removeprefix("wa_quote_mvp/") for name in archive.namelist()) + "\n"
        archive.writestr("wa_quote_mvp/SHA256SUMS.txt", hashes.encode("utf-8"))
    with zipfile.ZipFile(OUTPUT) as archive:
        assert archive.testzip() is None
        manifest = json.loads(archive.read("wa_quote_mvp/extension/manifest.json"))
        assert len(archive.namelist()) == len(set(archive.namelist()))
        assert manifest["version"] == "1.6.1"
        assert json.loads(archive.read("wa_quote_mvp/package.json"))["version"] == "1.6.1"
        assert archive.read("wa_quote_mvp/mobile/index.html")
        assert archive.read("wa_quote_mvp/backend/mobile_gateway.py")
        assert archive.read("wa_quote_mvp/extension/icon128.png").startswith(b"\x89PNG")
        assert archive.read("wa_quote_mvp/extension/content.css")
        assert archive.read("wa_quote_mvp/extension/theme.css")
        assert archive.read("wa_quote_mvp/extension/copilot.js")
        for name in ("business", "requirements", "requirement_tokens", "number_words", "reviews", "pricing"):
            assert archive.read(f"wa_quote_mvp/backend/{name}.py")
        assert not any("/data/" in n or "/.venv/" in n or "/node_modules/" in n or n.endswith(".sqlite3") for n in archive.namelist())
        assert archive.read("wa_quote_mvp/samples/products.xlsx").startswith(b"PK")
        assert archive.read("wa_quote_mvp/samples/business_demo.xlsx").startswith(b"PK")
        assert archive.read("wa_quote_mvp/队友使用指南_1.6.docx").startswith(b"PK")
        assert archive.read("wa_quote_mvp/docs/需求流程原文.docx").startswith(b"PK")
        assert b"PyMuPDF==1.26.6" in archive.read("wa_quote_mvp/requirements-dev.txt")
        assert json.loads(archive.read("wa_quote_mvp/qa-results/browser-results.json"))["passed_groups"] == 64
        assert b"331 passed" in archive.read("wa_quote_mvp/qa-results/backend-pytest.txt")
        assert archive.read("wa_quote_mvp/tests/test_retest_v151.py")
        assert archive.read("wa_quote_mvp/tests/test_audit_v152.py")
        assert archive.read("wa_quote_mvp/tests/audit_browser.mjs")
        assert archive.read("wa_quote_mvp/tests/test_release_startup.py")
        assert json.loads(archive.read("wa_quote_mvp/qa-results/upgrade-v160-v161.json"))["passed"]
        assert json.loads(archive.read("wa_quote_mvp/qa-results/long-inquiry-current.json"))["version"] == "1.6.1"
        assert archive.read("wa_quote_mvp/tests/test_limits_v153.py")
        assert archive.read("wa_quote_mvp/tests/ui_polish_browser.mjs")
        assert archive.read("wa_quote_mvp/retest-results/test_long_inquiry.py")
        assert archive.read("wa_quote_mvp/qa-results/long-inquiry-v154-after.json")
        assert b"waitForFunction" in archive.read("wa_quote_mvp/tests/copilot_browser.mjs")
        assert b"requirements_rules_v5" in archive.read("wa_quote_mvp/backend/requirement_tokens.py")
        assert b"requirements_rules_v5" in archive.read("wa_quote_mvp/extension/copilot.js")
        for line in archive.read("wa_quote_mvp/SHA256SUMS.txt").decode("utf-8").splitlines():
            digest, name = line.split("  ", 1)
            assert hashlib.sha256(archive.read("wa_quote_mvp/" + name)).hexdigest() == digest
        print(json.dumps({"path": str(OUTPUT), "files": len(archive.namelist()),
                          "bytes": OUTPUT.stat().st_size, "crc": "passed"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
