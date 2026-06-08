"""Smoke tests for ELECTIONLENS."""
import pytest
from electionlens.core import scan, TOOL_NAME, TOOL_VERSION
from cognis_core import ScanResult


def test_version():
    assert TOOL_VERSION


def test_scan_returns_result():
    result = scan("demos")
    assert isinstance(result, ScanResult)
    assert result.tool_name == TOOL_NAME


def test_cli_importable():
    from electionlens.cli import main
    assert callable(main)
