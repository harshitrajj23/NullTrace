"""code/tests/test_reproducibility.py

Test verifying reproducibility of the NullTrace submission candidate:
Pipeline output with overrides applied equals build/nulltrace_candidate_a3.csv byte for byte.
"""

import os
import sys
import tempfile
import pytest

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if "code" in sys.modules and not hasattr(sys.modules["code"], "src"):
    del sys.modules["code"]

try:
    from code.src.pipeline import run_integrated_pipeline, load_overrides
except ImportError:
    from src.pipeline import run_integrated_pipeline, load_overrides


def test_overrides_config_validity():
    """Verify code/config/overrides.csv exists, loads properly, and only sets INCOMPLETE."""
    overrides = load_overrides()
    assert len(overrides) == 9, f"Expected 9 overrides, got {len(overrides)}"
    for cid, ov in overrides.items():
        assert ov["final_status"] == "INCOMPLETE", f"Override for {cid} must be INCOMPLETE"
        assert ov["reason"], f"Override for {cid} must have a non-empty reason"
        assert ov["source_file"], f"Override for {cid} must cite a source file"


def test_overrides_only_allow_incomplete():
    """Verify that an override attempting to set a status other than INCOMPLETE raises ValueError."""
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as tf:
        tf.write("case_id,final_status,reason,source_file\n")
        tf.write("case_999,COMPLETE,invalid complete test,test.md\n")
        tf_path = tf.name

    try:
        with pytest.raises(ValueError, match="overrides may only set status to INCOMPLETE"):
            load_overrides(overrides_path=tf_path)
    finally:
        if os.path.exists(tf_path):
            os.remove(tf_path)


def test_pipeline_output_equals_candidate_a3_byte_for_byte():
    """Pipeline output with overrides applied equals build/nulltrace_candidate_a3.csv byte for byte."""
    candidate_a3_path = os.path.join(_repo_root, "build", "nulltrace_candidate_a3.csv")
    if not os.path.isfile(candidate_a3_path):
        pytest.skip("build/nulltrace_candidate_a3.csv not found (skipping in environment without build/)")

    data_dir = os.path.join(_repo_root, "dataset")
    with tempfile.TemporaryDirectory() as tmpdir:
        out_csv = os.path.join(tmpdir, "pipeline_out.csv")
        res = run_integrated_pipeline(data_dir=data_dir, output_path=out_csv)

        assert os.path.isfile(out_csv)
        with open(out_csv, "rb") as f_act, open(candidate_a3_path, "rb") as f_exp:
            act_bytes = f_act.read()
            exp_bytes = f_exp.read()

        assert len(act_bytes) == len(exp_bytes), (
            f"Byte length mismatch: actual {len(act_bytes)} vs expected {len(exp_bytes)}"
        )
        assert act_bytes == exp_bytes, "Pipeline output does not match candidate A3 byte for byte"
