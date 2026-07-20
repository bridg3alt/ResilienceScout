"""
Site-config regression tests.

Facility data lives in `sites/<id>.json`, loaded by presets at import. These pin the contract that
makes "bring your own facility" real: a site is a data file, the active one is selectable, and an
elevation quoted against external grade is converted through the datum machinery at load — not
pasted in pre-computed. They exercise the loader directly so they do not disturb the module-level
constants the rest of the suite reads.
"""
from __future__ import annotations

import json

import pytest

from resilienceos import presets


def test_default_site_is_the_decennial_block():
    assert presets.ACTIVE_SITE_ID == presets.DEFAULT_SITE_ID == "decennial_block"
    assert "decennial_block" in presets.available_sites()


def test_active_site_populates_the_public_constants_from_the_file():
    raw = json.loads(
        (presets.SITES_DIR / "decennial_block.json").read_text(encoding="utf-8")
    )
    assert presets.SHELTERS[0]["id"] == raw["id"]
    assert presets.POP_SERVED["decennial_block"] == raw["pop_served"]
    assert presets.FLOOD_LINE_M == raw["flood"]["observed_line_m"]
    assert presets.CRITICAL_LOAD_REPORTED_KW == raw["critical_load"]["reported_kw"]


def test_unknown_site_fails_loudly_rather_than_defaulting():
    with pytest.raises(FileNotFoundError, match="no site config"):
        presets._load_site("no_such_site")


def test_an_elevation_quoted_against_grade_is_converted_at_load():
    """A {value, datum} elevation is run through depth_above_floor, not stored pre-computed —
    so the file records what was surveyed and the datum machinery still owns the conversion."""
    assert presets._elevation(1.10) == 1.10
    converted = presets._elevation({"value": 0.10, "datum": "above_external_ground_m"})
    assert converted == pytest.approx(0.10 - presets.GROUND_TO_FLOOR_STEP_M)
    assert presets.EQUIPMENT_ELEVATION_M["road_access"] == converted
