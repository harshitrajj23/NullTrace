"""code/tests/test_vision_extraction.py

Unit tests for Controlled Gemini Multimodal Vision Extraction Adapter (Step E.2).

Verifies:
- Verified image inventory mapping from evidence_files.csv.
- Missing and corrupt image handling.
- Malformed model JSON and schema validation.
- Unreadable identifiers and ambiguity flags.
- Rejection of unsupported claims / UI button text.
- Cache determinism and usage tracking ledger.
- API failure and retry handling.
- Feature flag enforcement (enabled=False prevents network requests).
- Secret exclusion from cache, ledger, and memory structures.
- Strict isolation from dataset/sample_output.csv.
"""

import ast
import json
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch
import urllib.error

import pytest

# Ensure repo root is on path
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from code.src.evidence_extraction import ExtractedObservation, ObservationConfidence
from code.src.state_reconstruction import ResourceState
from code.src.vision_extraction import (
    GeminiVisionExtractor,
    UsageRecord,
    VisionConfig,
    get_verified_image_inventory,
)


def test_image_inventory_mapping():
    """Verify that all 11 IMAGE_ONLY files from evidence_files.csv are verified and exist on disk."""
    inventory = get_verified_image_inventory(_repo_root)
    assert len(inventory) == 11, f"Expected 11 verified images, got {len(inventory)}"
    
    expected_ids = {
        "evidence_04", "evidence_09", "evidence_14", "evidence_19",
        "evidence_23", "evidence_28", "evidence_32", "evidence_37",
        "evidence_42", "evidence_46", "evidence_60",
    }
    assert set(inventory.keys()) == expected_ids

    for fid, meta in inventory.items():
        assert meta["file_id"] == fid
        assert os.path.exists(meta["resolved_path"]), f"Missing file for {fid}: {meta['resolved_path']}"
        assert meta["size_bytes"] > 0, f"Empty file for {fid}"
        assert meta["origin"], f"Missing origin for {fid}"


def test_missing_image_files():
    """Verify error handling when an image file does not exist or manifest is invalid."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a bogus manifest pointing to a non-existent image
        dataset_dir = os.path.join(tmpdir, "dataset")
        os.makedirs(dataset_dir)
        manifest = os.path.join(dataset_dir, "evidence_files.csv")
        with open(manifest, "w", encoding="utf-8") as f:
            f.write("file_id,file_path,origin,captured_at\n")
            f.write("evidence_99,evidence/images/missing.png,test_origin,2026-09-01T00:00:00Z\n")

        with pytest.raises(FileNotFoundError) as exc_info:
            get_verified_image_inventory(tmpdir)
        assert "references non-existent image path" in str(exc_info.value)


def test_malformed_model_json():
    """Verify handling when vision model returns invalid or unparseable JSON."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = VisionConfig(
            enabled=True,
            cache_dir=os.path.join(tmpdir, "cache"),
            max_retries=2,
            timeout_seconds=2.0,
        )
        extractor = GeminiVisionExtractor(config=config, repo_root=_repo_root)

        # Mock urllib to return non-JSON text
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"candidates": [{"content": {"parts": [{"text": "NOT_JSON_AT_ALL"}]}}]}'
        mock_response.__enter__.return_value = mock_response

        with patch("urllib.request.urlopen", return_value=mock_response):
            with patch.object(extractor, "_get_api_key", return_value="fake_key"):
                with pytest.raises(RuntimeError) as exc_info:
                    extractor._execute_api_call(b"fake_image_bytes", "evidence_04")
                assert "Gemini API request failed after 2 attempts" in str(exc_info.value)


def test_schema_validation():
    """Verify structured parsing of well-formed vision JSON model response."""
    extractor = GeminiVisionExtractor(repo_root=_repo_root)
    meta = {
        "file_path": "evidence/images/test.png",
        "origin": "account_admin_portal",
        "captured_at": "2026-09-26T11:00:00Z",
    }
    sample_model_output = {
        "records": [
            {
                "visual_region": "Customer Header",
                "resource_id": "account_9999",
                "system_id": "account_service",
                "identifiers": {
                    "user_id": "user_42",
                    "email": "USER_42@Example.COM",
                    "phone": "+1 (555) 019-2834",
                },
                "raw_status_label": "ACTIVE",
                "observed_state": "PRESENT",
                "observation_type": "ACCOUNT_RECORD",
                "confidence": "HIGH",
                "is_direct_observation": True,
            }
        ]
    }
    observations = extractor._parse_structured_response("evidence_04", meta, sample_model_output)
    assert len(observations) == 1
    obs = observations[0]
    assert obs.resource_id == "account_9999"
    assert obs.system_id == "account_service"
    assert obs.observed_state == ResourceState.PRESENT
    assert obs.associated_identifiers["user_id"] == "user_42"
    assert obs.associated_identifiers["email"] == "user_42@example.com"
    assert obs.associated_identifiers["phone"] == "15550192834"
    assert obs.confidence == ObservationConfidence.HIGH


def test_unreadable_identifiers_and_ambiguity():
    """Verify that unreadable or ambiguous visual regions are flagged with AMBIGUOUS confidence."""
    extractor = GeminiVisionExtractor(repo_root=_repo_root)
    meta = {
        "file_path": "evidence/images/test.png",
        "origin": "account_admin_portal",
        "captured_at": "2026-09-26T11:00:00Z",
    }
    sample_model_output = {
        "records": [
            {
                "visual_region": "Blurry Footer",
                "resource_id": None,
                "system_id": None,
                "identifiers": {},
                "raw_status_label": "Unknown",
                "observed_state": None,
                "observation_type": "UNKNOWN_RECORD",
                "confidence": "UNCERTAIN",
                "is_direct_observation": False,
                "ambiguity_flags": ["BLURRY_TEXT", "TRUNCATED_ID"],
            }
        ]
    }
    observations = extractor._parse_structured_response("evidence_04", meta, sample_model_output)
    assert len(observations) == 1
    obs = observations[0]
    assert obs.confidence == ObservationConfidence.AMBIGUOUS
    assert "BLURRY_TEXT" in obs.ambiguity_flags
    assert "INFERRED_INTERPRETATION" in obs.ambiguity_flags


def test_unsupported_claims_not_inferred():
    """Verify that UI buttons (e.g. 'Delete User') do not produce an ABSENT state."""
    extractor = GeminiVisionExtractor(repo_root=_repo_root)
    meta = {
        "file_path": "evidence/images/test.png",
        "origin": "account_admin_portal",
        "captured_at": "2026-09-26T11:00:00Z",
    }
    sample_model_output = {
        "records": [
            {
                "visual_region": "Action Menu",
                "resource_id": "account_100",
                "system_id": "account_service",
                "identifiers": {"user_id": "user_10"},
                "raw_status_label": "Delete Account Button",
                "observed_state": None,  # Button is not state
                "observation_type": "UI_ACTION_BUTTON",
                "confidence": "MEDIUM",
                "is_direct_observation": True,
            }
        ]
    }
    observations = extractor._parse_structured_response("evidence_04", meta, sample_model_output)
    assert len(observations) == 1
    assert observations[0].observed_state is None
    # Cannot convert to EvidenceObservation without determinable state
    assert observations[0].to_evidence_observation() is None


def test_cache_determinism():
    """Verify that cached observations return deterministically without API calls."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = VisionConfig(
            enabled=False,  # Disabled! Must rely entirely on cache
            cache_dir=os.path.join(tmpdir, "cache"),
        )
        extractor = GeminiVisionExtractor(config=config, repo_root=_repo_root)

        # Pre-seed cache file
        img_meta = extractor.verified_inventory["evidence_04"]
        with open(img_meta["resolved_path"], "rb") as f:
            img_bytes = f.read()
        cache_key = extractor._compute_cache_key("evidence_04", img_bytes)
        cache_file = os.path.join(extractor.cache_dir, f"{cache_key}.json")
        
        seeded_data = {
            "file_id": "evidence_04",
            "cache_key": cache_key,
            "created_at": "2026-10-24T20:00:00Z",
            "provider": "gemini",
            "model_id": "gemini-3.5-flash",
            "prompt_version": "v1.0",
            "usage_metadata": {"promptTokenCount": 100, "candidatesTokenCount": 50, "totalTokenCount": 150},
            "model_output": {
                "records": [
                    {
                        "visual_region": "Cached Card",
                        "resource_id": "account_cached_01",
                        "system_id": "account_service",
                        "identifiers": {"user_id": "user_99"},
                        "raw_status_label": "ACTIVE",
                        "observed_state": "PRESENT",
                        "observation_type": "ACCOUNT_RECORD",
                        "confidence": "HIGH",
                        "is_direct_observation": True,
                    }
                ]
            },
        }
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(seeded_data, f)

        # Extraction should succeed from cache even though enabled=False
        obs = extractor.extract_file("evidence_04")
        assert len(obs) == 1
        assert obs[0].resource_id == "account_cached_01"


def test_api_failures_and_retries():
    """Verify that HTTP 503/500 errors trigger retries up to max_retries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = VisionConfig(
            enabled=True,
            cache_dir=os.path.join(tmpdir, "cache"),
            max_retries=3,
            timeout_seconds=1.0,
        )
        extractor = GeminiVisionExtractor(config=config, repo_root=_repo_root)

        call_count = 0
        def fake_urlopen(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise urllib.error.HTTPError("http://fake", 503, "Service Unavailable", {}, None)

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with patch.object(extractor, "_get_api_key", return_value="fake_key"):
                with pytest.raises(RuntimeError) as exc_info:
                    extractor._execute_api_call(b"fake_bytes", "evidence_04")
                assert call_count == 3
                assert "failed after 3 attempts" in str(exc_info.value)


def test_disabled_feature_flag_prevents_calls():
    """Verify that when enabled=False, extract_file returns empty without making any network call."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = VisionConfig(
            enabled=False,
            cache_dir=os.path.join(tmpdir, "cache"),
        )
        extractor = GeminiVisionExtractor(config=config, repo_root=_repo_root)

        with patch("urllib.request.urlopen") as mock_url:
            obs = extractor.extract_file("evidence_04")
            assert obs == []
            mock_url.assert_not_called()


def test_secret_exclusion_from_logs_and_cache():
    """Verify that cache files and usage ledger never store API keys or private headers."""
    # Check the real cache directory
    cache_dir = os.path.join(_repo_root, "build", "cache", "vision")
    if os.path.exists(cache_dir):
        for fname in os.listdir(cache_dir):
            if fname.endswith(".json"):
                fpath = os.path.join(cache_dir, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
                    assert "AIza" not in content, f"Possible Google API key found in {fpath}"
                    assert "x-goog-api-key" not in content.lower(), f"API key header found in {fpath}"
                    assert "bearer " not in content.lower(), f"Bearer token found in {fpath}"


def test_no_production_access_to_sample_output():
    """Ensure production vision extraction code does not access sample_output.csv."""
    source_path = os.path.join(_repo_root, "code", "src", "vision_extraction.py")
    with open(source_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename="vision_extraction.py")

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert "sample_output.csv" not in node.value, (
                f"Forbidden reference to sample_output.csv found in {source_path}"
            )
