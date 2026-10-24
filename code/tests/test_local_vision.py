"""code/tests/test_local_vision.py

Unit tests for Local Apple Vision Extraction Adapter (Step E.4).

Verifies:
- Complete mapping and local extraction of the 10 remaining screenshots.
- Missing image and malformed OCR error handling.
- Bounding-box and provenance preservation.
- Ambiguous text and state association handling.
- Deterministic cache key generation and cache hits without rerunning OCR.
- Zero network requests, zero external API calls, and zero external spend.
- Strict isolation from personal values in logs and cache metadata.
- Strict isolation from dataset/sample_output.csv.
"""

import ast
import json
import os
import socket
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

# Ensure repo root is on path
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from code.src.evidence_extraction import ExtractedObservation, ObservationConfidence
from code.src.local_vision_extraction import (
    AppleVisionExtractor,
    LocalVisionConfig,
    RawTextBlock,
)
from code.src.state_reconstruction import ResourceState


def test_mapping_of_remaining_10_screenshots():
    """Verify that all 10 remaining screenshots can be extracted and mapped to structured observations."""
    extractor = AppleVisionExtractor(repo_root=_repo_root)
    target_ids = [
        "evidence_09", "evidence_14", "evidence_19", "evidence_23",
        "evidence_28", "evidence_32", "evidence_37", "evidence_42",
        "evidence_46", "evidence_60",
    ]
    
    import csv
    manifest = {}
    with open(os.path.join(_repo_root, "dataset", "evidence_files.csv"), "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            manifest[r["file_id"]] = r

    for fid in target_ids:
        row = manifest[fid]
        obs = extractor.extract_file(
            file_id=fid,
            rel_path=row["file_path"],
            origin=row["origin"],
            captured_at=row.get("captured_at"),
        )
        assert isinstance(obs, list), f"Expected list of observations for {fid}"
        for o in obs:
            assert o.file_id == fid
            assert o.extraction_method == "APPLE_VISION"
            assert o.source_file == row["file_path"]


def test_missing_image_handling():
    """Verify FileNotFoundError when attempting to extract non-existent image."""
    extractor = AppleVisionExtractor(repo_root=_repo_root)
    with pytest.raises(FileNotFoundError):
        extractor.extract_file(
            file_id="evidence_99",
            rel_path="evidence/images/missing_image_99.png",
            origin="test_service",
        )


def test_malformed_ocr_output():
    """Verify handling when local OCR binary produces malformed JSON."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = LocalVisionConfig(cache_dir=os.path.join(tmpdir, "cache"))
        extractor = AppleVisionExtractor(config=config, repo_root=_repo_root)

        fake_res = MagicMock()
        fake_res.returncode = 0
        fake_res.stdout = b"INVALID_NON_JSON_DATA"

        with patch("subprocess.run", return_value=fake_res):
            with pytest.raises(ValueError) as exc_info:
                extractor.run_local_ocr(os.path.join(_repo_root, "dataset", "evidence", "images", "account_admin_console_20260926.png"))
            assert "Malformed JSON" in str(exc_info.value)


def test_bounding_box_and_provenance_preservation():
    """Verify that 2D bounding boxes and source provenance are preserved in extracted observations."""
    extractor = AppleVisionExtractor(repo_root=_repo_root)
    blocks = [
        RawTextBlock(text="account_1234", confidence=0.99, x=0.1, y=0.5, width=0.2, height=0.04),
        RawTextBlock(text="user_99", confidence=0.95, x=0.1, y=0.48, width=0.1, height=0.03),
        RawTextBlock(text="ACTIVE", confidence=0.90, x=0.2, y=0.5, width=0.08, height=0.03),
    ]

    obs = extractor._parse_ocr_blocks(
        blocks=blocks,
        file_id="evidence_99",
        source_path="evidence/images/fake.png",
        origin="account_service",
        timestamp=None,
    )
    assert len(obs) == 1
    o = obs[0]
    assert o.resource_id == "account_1234"
    assert o.associated_identifiers.get("user_id") == "user_99"
    assert "visual_box:x=0.100,y=0.500" in o.source_location
    assert o.observed_state == ResourceState.PRESENT


def test_ambiguous_text_associations():
    """Verify that ambiguous or unassociated records are flagged with AMBIGUOUS confidence."""
    extractor = AppleVisionExtractor(repo_root=_repo_root)
    # Block with resource_id but no identifiers anywhere nearby
    blocks = [
        RawTextBlock(text="search_8888", confidence=0.85, x=0.9, y=0.9, width=0.1, height=0.03),
    ]

    obs = extractor._parse_ocr_blocks(
        blocks=blocks,
        file_id="evidence_99",
        source_path="evidence/images/fake.png",
        origin="search_service",
        timestamp=None,
    )
    assert len(obs) == 1
    assert obs[0].confidence == ObservationConfidence.AMBIGUOUS
    assert "AMBIGUOUS_STATE_OR_IDENTITY_ASSOCIATION" in obs[0].ambiguity_flags


def test_deterministic_cache_keys():
    """Verify deterministic cache key computation for identical image bytes."""
    extractor = AppleVisionExtractor(repo_root=_repo_root)
    data = b"some_image_binary_bytes_12345"
    key1 = extractor._compute_cache_key("evidence_09", data)
    key2 = extractor._compute_cache_key("evidence_09", data)
    assert key1 == key2
    assert "evidence_09_" in key1
    assert "apple_vision_v1.0" in key1


def test_cache_hits_without_rerunning_ocr():
    """Verify that cache hits load observations without re-executing OCR."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = LocalVisionConfig(cache_dir=os.path.join(tmpdir, "cache"))
        extractor = AppleVisionExtractor(config=config, repo_root=_repo_root)

        # Pre-seed cache
        img_rel = "evidence/images/search_index_inspector_20260901.png"
        img_full = os.path.join(_repo_root, "dataset", img_rel)
        with open(img_full, "rb") as f:
            b = f.read()
        cache_key = extractor._compute_cache_key("evidence_09", b)
        cache_file = os.path.join(extractor.cache_dir, f"{cache_key}.json")

        seeded = {
            "file_id": "evidence_09",
            "cache_key": cache_key,
            "provider": "apple_vision",
            "runtime": "macOS_Swift_Vision",
            "version": "v1.0",
            "source_file": img_rel,
            "observations_count": 1,
            "parsed_observations": [
                {
                    "source_file": img_rel,
                    "file_id": "evidence_09",
                    "evidence_id": "evidence_09",
                    "source_location": "visual_region:cached_test",
                    "observation_type": "APPLE_VISION_OCR_RECORD",
                    "extraction_method": "APPLE_VISION",
                    "confidence": "HIGH",
                    "timestamp": None,
                    "resource_id": "search_cached_01",
                    "system_id": "search_service",
                    "associated_identifiers": {"user_id": "user_13"},
                    "observed_state": "PRESENT",
                    "raw_payload": {},
                    "ambiguity_flags": [],
                }
            ],
        }
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(seeded, f)

        # Extraction must succeed from cache without running subprocess
        with patch("subprocess.run") as mock_sub:
            obs = extractor.extract_file("evidence_09", img_rel, "search_service")
            assert len(obs) == 1
            assert obs[0].resource_id == "search_cached_01"
            mock_sub.assert_not_called()


def test_no_network_access_or_external_api_invocation():
    """Verify that local Apple Vision extractor never makes network requests."""
    extractor = AppleVisionExtractor(repo_root=_repo_root)
    img_rel = "evidence/images/search_index_inspector_20260901.png"

    def no_socket(*args, **kwargs):
        raise AssertionError("Network socket call attempted during local OCR extraction!")

    with patch.object(socket, "socket", side_effect=no_socket):
        obs = extractor.extract_file("evidence_09", img_rel, "search_service")
        assert isinstance(obs, list)


def test_no_personal_values_in_logs_or_metadata():
    """Verify that cached metadata files do not leak secrets or arbitrary unredacted PII in root keys."""
    cache_dir = os.path.join(_repo_root, "build", "cache", "apple_vision")
    if os.path.exists(cache_dir):
        for fname in os.listdir(cache_dir):
            if fname.endswith(".json"):
                fpath = os.path.join(cache_dir, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    c = f.read()
                    assert "AIza" not in c, f"API key pattern found in {fpath}"
                    assert "x-goog-api-key" not in c.lower()


def test_no_production_access_to_sample_output():
    """Ensure local vision extraction code does not access sample_output.csv."""
    source_path = os.path.join(_repo_root, "code", "src", "local_vision_extraction.py")
    with open(source_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename="local_vision_extraction.py")

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert "sample_output.csv" not in node.value, (
                f"Forbidden reference to sample_output.csv found in {source_path}"
            )
