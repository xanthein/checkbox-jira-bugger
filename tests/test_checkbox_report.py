import json
import os
from checkbox_jira_bugger import checkbox_report

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_submission():
    with open(os.path.join(FIXTURES, "submission.json")) as f:
        return json.load(f)


def test_get_manifest_and_device_information_on_real_fixture():
    data = _load_submission()
    manifest_name, manifest_version, bios_version, sku_number = (
        checkbox_report.get_manifest_and_device_information(data)
    )
    # The real fixture is a stella/noble image; assert we get non-"unknown" values,
    # proving the parser handles a real submission without a KeyError.
    assert manifest_name != "unknown"
    assert bios_version != "unknown"


def test_get_ubuntu_version_on_real_fixture():
    data = _load_submission()
    version = checkbox_report.get_ubuntu_version(data)
    assert version is not None


def test_is_valid_sku_name():
    assert checkbox_report.is_valid_sku_name("Thor3-AMD-1_202308-32003")
    assert not checkbox_report.is_valid_sku_name("")


def test_apply_cve_buffer_rule_no_cvescan_job_is_noop():
    data = {"results": [{"id": "some/other/job", "status": "fail"}]}
    # Should not raise even though there's no miscellanea/cvescan job present.
    checkbox_report.apply_cve_buffer_rule(data)


def test_format_bug_returns_title_and_description():
    title, description = checkbox_report.format_bug(
        manifest_name="stella-manifest",
        manifest_version="20260901-458",
        test_id="audio/playback",
        certification_status="blocker",
        test_iolog="some io log",
        test_full_id="com.canonical.certification::audio/playback",
        bios_version="1.02.01",
        sku_number="SKU123",
        sku_name="Thor3-AMD-1_202308-32003",
        tester="auto-sanity-bot",
    )
    assert "audio/playback" in title or "audio/playback" in description
    assert isinstance(title, str)
    assert isinstance(description, str)


KW = dict(
    manifest_name="stella-manifest",
    manifest_version="20260901-458",
    test_id="audio/playback",
    certification_status="blocker",
    test_iolog="some io log",
    test_full_id="com.canonical.certification::audio/playback",
    bios_version="1.02.01",
    sku_number="SKU123",
    sku_name="Thor3-AMD-1_202308-32003",
    tester="auto-sanity-bot",
)


def test_format_bug_description_uses_wiki_layout():
    _, d = checkbox_report.format_bug(**KW)
    for h in ["[Summary]", "[I/O log]", "[Reproduce Steps]", "[Results]", "[Additional Information]"]:
        assert f"h3. {h}" in d
    assert "{noformat}\nsome io log\n{noformat}" in d
    assert "# sudo checkbox-cli run com.canonical.certification::audio/playback" in d
    for line in ["Manifest: stella-manifest 20260901-458", "BIOS Version: 1.02.01",
                 "SKU: Thor3-AMD-1_202308-32003", "BIOS ID: SKU123", "Tester: auto-sanity-bot"]:
        assert line in d
    assert "Manifest: stella-manifest 20260901-458\n\nBIOS Version: 1.02.01" in d


def test_format_bug_escapes_noformat_in_iolog():
    _, d = checkbox_report.format_bug(**{**KW, "test_iolog": "a {noformat} b"})
    assert "a \\{noformat} b" in d
    assert d.count("{noformat}") - d.count("\\{noformat}") == 2


def test_format_bug_empty_iolog():
    _, d = checkbox_report.format_bug(**{**KW, "test_iolog": ""})
    assert "{noformat}\n\n{noformat}" in d
