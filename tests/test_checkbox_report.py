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


def test_format_bug_description_separates_every_meaningful_line_with_a_blank_line():
    """
    Regression test confirmed against a real Jira Cloud issue (STELLA-4127):
    when this description is submitted to Jira (as a plain string, via the
    v2-compatible write path), Jira's storage layer silently drops single
    "\\n" line breaks entirely (with zero separator, not even a space) --
    only a blank line ("\\n\\n") survives, converted to a real line break.
    Every field in [Additional Information] (Manifest/BIOS Version/SKU/
    BIOS ID/Tester) must therefore be separated by a blank line, or they get
    jammed together on Jira's side and become unparseable by
    get_bug_manifest_version/get_bug_manifest_name/get_bug_skus.
    """
    _, description = checkbox_report.format_bug(
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
    manifest_line = "Manifest: stella-manifest 20260901-458"
    bios_line = "BIOS Version: 1.02.01"
    sku_line = "SKU: Thor3-AMD-1_202308-32003"
    bios_id_line = "BIOS ID: SKU123"
    tester_line = "Tester: auto-sanity-bot"

    assert f"{manifest_line}\n\n{bios_line}" in description
    assert f"{bios_line}\n\n{sku_line}" in description
    assert f"{sku_line}\n\n{bios_id_line}" in description
    assert f"{bios_id_line}\n\n{tester_line}" in description
