"""code/src/evidence_coverage.py

Corpus & Case-Level Evidence Coverage Tracker for HackerRank Orchestrate: Ghost Data Still Exists.

Tracks evidence extraction coverage at two explicit levels:
1. File-level extraction coverage:
   - PARSED_WITH_OBSERVATIONS
   - PARSED_NO_RELEVANT_OBSERVATIONS
   - REQUIRES_OCR
   - UNREADABLE
   - PARSER_ERROR
2. Case-level relevant evidence coverage:
   - Accounts for all modalities (JSON, SQL, LOG, PDF, TEXT, IMAGE).
   - Preserves uncertainty: a successfully parsed file with no matching subject is not proof
     that the subject's data is absent across the platform.
   - Strictly prevents false claims of complete corpus inspection when modalities
     (such as administrative console screenshots) remain uninspected.
"""

import csv
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
import os
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

# Standard library module 'code' conflict resolution
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if "code" in sys.modules and not hasattr(sys.modules["code"], "src"):
    del sys.modules["code"]

try:
    from code.src.evidence_extraction import (
        ExtractedObservation,
        JsonRecordExtractor,
        LogRecordExtractor,
        ObservationConfidence,
        PdfDocumentExtractor,
        PlainTextExtractor,
        SqlSnapshotExtractor,
    )
    from code.src.normalize import normalize_email, normalize_phone, normalize_timestamp
    from code.src.state_reconstruction import parse_timestamp_to_utc
except ImportError:
    from src.evidence_extraction import (
        ExtractedObservation,
        JsonRecordExtractor,
        LogRecordExtractor,
        ObservationConfidence,
        PdfDocumentExtractor,
        PlainTextExtractor,
        SqlSnapshotExtractor,
    )
    from src.normalize import normalize_email, normalize_phone, normalize_timestamp
    from src.state_reconstruction import parse_timestamp_to_utc

logger = logging.getLogger("nulltrace.evidence_coverage")


class FileCoverageStatus(str, Enum):
    """File-level extraction status."""
    PARSED_WITH_OBSERVATIONS = "PARSED_WITH_OBSERVATIONS"
    PARSED_NO_RELEVANT_OBSERVATIONS = "PARSED_NO_RELEVANT_OBSERVATIONS"
    REQUIRES_OCR = "REQUIRES_OCR"
    UNREADABLE = "UNREADABLE"
    PARSER_ERROR = "PARSER_ERROR"


@dataclass
class FileCoverageReport:
    """Extraction audit report for an individual evidence file."""
    file_id: str
    file_path: str
    modality: str                               # JSON, SQL, LOG, PDF, TEXT, IMAGE, UNKNOWN
    status: FileCoverageStatus
    total_observations: int
    error_message: Optional[str] = None
    requires_vision_model: bool = False
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CorpusCoverageSummary:
    """Aggregated coverage report across the entire evidence corpus."""
    total_files: int
    files_by_modality: Dict[str, int]
    files_by_status: Dict[str, int]
    total_observations_extracted: int
    observations_by_modality: Dict[str, int]
    file_reports: Dict[str, FileCoverageReport] = field(default_factory=dict)
    all_observations: List[ExtractedObservation] = field(default_factory=list)


@dataclass
class CaseCoverageResult:
    """Case-level relevant evidence coverage result."""
    case_id: str
    total_corpus_files: int
    relevant_files_count: int
    relevant_observations_count: int
    modalities_with_evidence: Set[str]
    uninspected_or_pending_modalities: Set[str]
    is_fully_covered: bool
    relevant_file_ids: List[str]
    coverage_gaps: List[str]
    audit_notes: Dict[str, Any] = field(default_factory=dict)


def detect_modality(file_path: str) -> str:
    """Detects canonical evidence modality from file extension."""
    ext = os.path.splitext(file_path)[1].lower()
    mapping = {
        ".json": "JSON",
        ".sql": "SQL",
        ".log": "LOG",
        ".pdf": "PDF",
        ".txt": "TEXT",
        ".png": "IMAGE",
        ".jpg": "IMAGE",
        ".jpeg": "IMAGE",
    }
    return mapping.get(ext, "UNKNOWN")


class CorpusCoverageTracker:
    """
    Manages end-to-end extraction across the evidence corpus and tracks
    file-level and case-level coverage.
    """

    def __init__(self, data_dir: str = "./dataset"):
        self.data_dir = data_dir
        self.summary: Optional[CorpusCoverageSummary] = None
        self._obs_by_resource: Dict[str, List[ExtractedObservation]] = {}
        self._obs_by_identifier: Dict[str, List[ExtractedObservation]] = {}

    def extract_corpus(self) -> CorpusCoverageSummary:
        """Parses all evidence files listed in evidence_files.csv and records coverage."""
        manifest_path = os.path.join(self.data_dir, "evidence_files.csv")
        file_reports: Dict[str, FileCoverageReport] = {}
        all_obs: List[ExtractedObservation] = []

        files_by_modality: Dict[str, int] = {}
        files_by_status: Dict[str, int] = {}
        obs_by_modality: Dict[str, int] = {}

        if not os.path.isfile(manifest_path):
            logger.error(f"Manifest not found: {manifest_path}")
            return CorpusCoverageSummary(0, {}, {}, 0, {})

        manifest_rows = []
        with open(manifest_path, "r", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                manifest_rows.append(r)

        for row in manifest_rows:
            fid = row["file_id"]
            rel_path = row["file_path"].replace("\\", "/")
            full_path = os.path.join(self.data_dir, rel_path.replace("evidence/", "evidence/"))
            modality = detect_modality(rel_path)
            files_by_modality[modality] = files_by_modality.get(modality, 0) + 1

            cap_time = parse_timestamp_to_utc(row.get("captured_at"))

            # 1. Image Modality
            if modality == "IMAGE":
                file_reports[fid] = FileCoverageReport(
                    file_id=fid,
                    file_path=rel_path,
                    modality=modality,
                    status=FileCoverageStatus.REQUIRES_OCR,
                    total_observations=0,
                    requires_vision_model=True,
                    details={"reason": "Administrative console screenshot requires vision-model interpretation"},
                )
                files_by_status[FileCoverageStatus.REQUIRES_OCR.value] = (
                    files_by_status.get(FileCoverageStatus.REQUIRES_OCR.value, 0) + 1
                )
                continue

            # Check file existence
            if not os.path.isfile(full_path):
                file_reports[fid] = FileCoverageReport(
                    file_id=fid,
                    file_path=rel_path,
                    modality=modality,
                    status=FileCoverageStatus.UNREADABLE,
                    total_observations=0,
                    error_message=f"File not found at: {full_path}",
                )
                files_by_status[FileCoverageStatus.UNREADABLE.value] = (
                    files_by_status.get(FileCoverageStatus.UNREADABLE.value, 0) + 1
                )
                continue

            # 2. Extract based on modality
            try:
                obs: List[ExtractedObservation] = []
                req_ocr = False

                if modality == "JSON":
                    obs = JsonRecordExtractor.extract(full_path, fid, cap_time)
                elif modality == "SQL":
                    obs = SqlSnapshotExtractor.extract(full_path, fid, cap_time)
                elif modality == "LOG":
                    obs = LogRecordExtractor.extract(full_path, fid, cap_time)
                elif modality == "TEXT":
                    obs = PlainTextExtractor.extract(full_path, fid, cap_time)
                elif modality == "PDF":
                    obs, req_ocr = PdfDocumentExtractor.extract(full_path, fid, cap_time)
                else:
                    file_reports[fid] = FileCoverageReport(
                        file_id=fid,
                        file_path=rel_path,
                        modality=modality,
                        status=FileCoverageStatus.UNREADABLE,
                        total_observations=0,
                        error_message=f"Unsupported modality: {modality}",
                    )
                    files_by_status[FileCoverageStatus.UNREADABLE.value] = (
                        files_by_status.get(FileCoverageStatus.UNREADABLE.value, 0) + 1
                    )
                    continue

                if req_ocr:
                    st = FileCoverageStatus.REQUIRES_OCR
                    requires_vm = True
                elif obs:
                    st = FileCoverageStatus.PARSED_WITH_OBSERVATIONS
                    requires_vm = False
                else:
                    st = FileCoverageStatus.PARSED_NO_RELEVANT_OBSERVATIONS
                    requires_vm = False

                file_reports[fid] = FileCoverageReport(
                    file_id=fid,
                    file_path=rel_path,
                    modality=modality,
                    status=st,
                    total_observations=len(obs),
                    requires_vision_model=requires_vm,
                )
                files_by_status[st.value] = files_by_status.get(st.value, 0) + 1
                obs_by_modality[modality] = obs_by_modality.get(modality, 0) + len(obs)

                all_obs.extend(obs)

            except Exception as e:
                logger.error(f"Parser error on {fid} ({full_path}): {e}")
                file_reports[fid] = FileCoverageReport(
                    file_id=fid,
                    file_path=rel_path,
                    modality=modality,
                    status=FileCoverageStatus.PARSER_ERROR,
                    total_observations=0,
                    error_message=str(e),
                )
                files_by_status[FileCoverageStatus.PARSER_ERROR.value] = (
                    files_by_status.get(FileCoverageStatus.PARSER_ERROR.value, 0) + 1
                )

        # Index observations for fast case-level lookup
        self._obs_by_resource.clear()
        self._obs_by_identifier.clear()

        for o in all_obs:
            if o.resource_id:
                self._obs_by_resource.setdefault(o.resource_id, []).append(o)
            for k, val in o.associated_identifiers.items():
                if val:
                    self._obs_by_identifier.setdefault(val.strip().lower(), []).append(o)

        self.summary = CorpusCoverageSummary(
            total_files=len(manifest_rows),
            files_by_modality=files_by_modality,
            files_by_status=files_by_status,
            total_observations_extracted=len(all_obs),
            observations_by_modality=obs_by_modality,
            file_reports=file_reports,
            all_observations=all_obs,
        )
        return self.summary

    def evaluate_case_coverage(
        self,
        case_id: str,
        subject_identifiers: Set[str],
        resource_ids: Set[str],
    ) -> CaseCoverageResult:
        """
        Evaluates case-level evidence coverage:
        - Cross-references subject identifiers and resource IDs against corpus observations.
        - Identifies modalities with grounded evidence vs uninspected modalities.
        - Enforces fail-closed: is_fully_covered is False if IMAGE modality is uninspected
          or if any modality remains unverified.
        """
        if self.summary is None:
            self.extract_corpus()

        relevant_obs: List[ExtractedObservation] = []
        relevant_file_ids: Set[str] = set()
        modalities_found: Set[str] = set()
        seen_obs_locs: Set[str] = set()

        # Match by resource IDs
        for rid in resource_ids:
            for o in self._obs_by_resource.get(rid, []):
                k = (o.file_id, o.source_location, o.resource_id)
                if k not in seen_obs_locs:
                    seen_obs_locs.add(k)
                    relevant_obs.append(o)
                    relevant_file_ids.add(o.file_id)
                    mod = detect_modality(o.source_file)
                    modalities_found.add(mod)

        # Match by subject identifiers
        for raw_id in subject_identifiers:
            norm_id = raw_id.strip().lower()
            for o in self._obs_by_identifier.get(norm_id, []):
                k = (o.file_id, o.source_location, o.resource_id)
                if k not in seen_obs_locs:
                    seen_obs_locs.add(k)
                    relevant_obs.append(o)
                    relevant_file_ids.add(o.file_id)
                    mod = detect_modality(o.source_file)
                    modalities_found.add(mod)

        # Check uninspected or pending modalities
        uninspected_modalities: Set[str] = set()
        gaps: List[str] = []

        # 1. Images / Screenshots are uninspected without vision models
        uninspected_modalities.add("IMAGE")
        gaps.append("Administrative console screenshots require vision-model interpretation")

        # 2. If no resources were identified, flag coverage gap
        if not resource_ids:
            gaps.append("No system resources identified for subject; coverage incomplete")

        # 3. Completeness signal
        is_fully_covered = (len(uninspected_modalities) == 0) and (len(resource_ids) > 0)

        return CaseCoverageResult(
            case_id=case_id,
            total_corpus_files=self.summary.total_files if self.summary else 0,
            relevant_files_count=len(relevant_file_ids),
            relevant_observations_count=len(relevant_obs),
            modalities_with_evidence=modalities_found,
            uninspected_or_pending_modalities=uninspected_modalities,
            is_fully_covered=is_fully_covered,
            relevant_file_ids=sorted(relevant_file_ids),
            coverage_gaps=gaps,
            audit_notes={
                "matched_resources_count": len(resource_ids),
                "matched_identifiers_count": len(subject_identifiers),
            },
        )

    def build_resource_evidence_map(
        self,
        case_id: str,
        resource_ids: Set[str],
    ) -> Dict[str, Set[str]]:
        """
        Builds a map of resource_id -> Set[evidence_id] containing only verified
        supporting evidence IDs extracted from the corpus for that resource.
        """
        if self.summary is None:
            self.extract_corpus()

        res_ev_map: Dict[str, Set[str]] = {}
        for rid in resource_ids:
            ev_set = set()
            for o in self._obs_by_resource.get(rid, []):
                if o.evidence_id:
                    ev_set.add(o.evidence_id)
            res_ev_map[rid] = ev_set

        return res_ev_map
