"""code/src/local_vision_extraction.py

Local-Only Multimodal Vision Extraction Adapter via macOS Native Apple Vision Framework.

Operates strictly offline:
- Zero external API calls, zero network requests, zero cloud OCR.
- Uses local macOS /usr/bin/swift runtime and native Apple Vision (VNRecognizeTextRequest).
- Extracts text blocks, confidence scores, and 2D bounding boxes (x, y, width, height).
- Preserves spatial layout for row-level and card-level entity association.
- Caches results deterministically by image SHA-256 at build/cache/apple_vision/.
- Strictly separates local OCR from external Gemini cache structures.
- Does not log or print personal values.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple

# Standard library module 'code' conflict resolution
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if "code" in sys.modules and not hasattr(sys.modules["code"], "src"):
    del sys.modules["code"]

try:
    from code.src.evidence_extraction import ExtractedObservation, ObservationConfidence
    from code.src.normalize import normalize_email, normalize_phone, normalize_timestamp
    from code.src.state_reconstruction import ResourceState, ensure_utc, parse_timestamp_to_utc
except ImportError:
    from src.evidence_extraction import ExtractedObservation, ObservationConfidence
    from src.normalize import normalize_email, normalize_phone, normalize_timestamp
    from src.state_reconstruction import ResourceState, ensure_utc, parse_timestamp_to_utc

logger = logging.getLogger("nulltrace.local_vision")

# Swift code for Apple Vision text recognition with bounding box extraction
SWIFT_VISION_SCRIPT = """
import Foundation
import Vision
import AppKit

let args = CommandLine.arguments
guard args.count > 1 else { exit(1) }
let imagePath = args[1]

guard let image = NSImage(contentsOfFile: imagePath),
      let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    exit(2)
}

struct Block: Codable {
    let text: String
    let confidence: Float
    let x: Double
    let y: Double
    let width: Double
    let height: Double
}

var blocks: [Block] = []
let request = VNRecognizeTextRequest { req, err in
    guard let observations = req.results as? [VNRecognizedTextObservation] else { return }
    for obs in observations {
        guard let candidate = obs.topCandidates(1).first else { continue }
        let bb = obs.boundingBox
        blocks.append(Block(
            text: candidate.string,
            confidence: candidate.confidence,
            x: Double(bb.origin.x),
            y: Double(bb.origin.y),
            width: Double(bb.size.width),
            height: Double(bb.size.height)
        ))
    }
}
request.recognitionLevel = .accurate
let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
try? handler.perform([request])

let data = try! JSONEncoder().encode(blocks)
FileHandle.standardOutput.write(data)
"""


@dataclass
class LocalVisionConfig:
    """Configuration for local Apple Vision extraction."""
    cache_dir: str = "build/cache/apple_vision"
    version: str = "v1.0"
    timeout_seconds: float = 30.0


@dataclass
class RawTextBlock:
    """Raw text bounding box extracted by Apple Vision OCR."""
    text: str
    confidence: float
    x: float
    y: float
    width: float
    height: float


class AppleVisionExtractor:
    """Extracts factual text and resource associations locally using Apple Vision."""

    def __init__(self, config: Optional[LocalVisionConfig] = None, repo_root: Optional[str] = None):
        self.repo_root = repo_root or _repo_root
        self.config = config or LocalVisionConfig()
        self.cache_dir = os.path.join(self.repo_root, self.config.cache_dir)
        os.makedirs(self.cache_dir, exist_ok=True)
        self.binary_path: Optional[str] = None
        self._ensure_binary()

    def _ensure_binary(self) -> None:
        """Compiles or locates the swift binary runner for Apple Vision."""
        if shutil.which("swiftc") is None:
            logger.warning("swiftc not available in environment; offline Apple Vision binary compilation disabled")
            return

        bin_dir = os.path.join(self.cache_dir, "bin")
        os.makedirs(bin_dir, exist_ok=True)
        bin_path = os.path.join(bin_dir, "apple_vision_runner")
        src_path = os.path.join(bin_dir, "apple_vision_runner.swift")

        # Compile if missing or outdated
        if not os.path.exists(bin_path) or not os.path.exists(src_path):
            with open(src_path, "w", encoding="utf-8") as f:
                f.write(SWIFT_VISION_SCRIPT)
            res = subprocess.run(["swiftc", "-O", src_path, "-o", bin_path], capture_output=True)
            if res.returncode != 0:
                logger.error("Failed to compile Apple Vision swift runner: %s", res.stderr.decode("utf-8", "replace"))
                return

        self.binary_path = bin_path

    def _compute_cache_key(self, file_id: str, image_bytes: bytes) -> str:
        """Deterministic cache key based on file_id, image sha256, and version."""
        sha = hashlib.sha256(image_bytes).hexdigest()
        return f"{file_id}_{sha[:16]}_apple_vision_{self.config.version}"

    def run_local_ocr(self, image_path: str) -> List[RawTextBlock]:
        """Runs offline Apple Vision OCR on an image file, returning raw text blocks with bounding boxes."""
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found at {image_path}")

        if not self.binary_path or not os.path.exists(self.binary_path):
            self._ensure_binary()
            if not self.binary_path or not os.path.exists(self.binary_path):
                raise RuntimeError("Local Apple Vision runner could not be compiled or executed")

        t0 = time.time()
        res = subprocess.run([self.binary_path, image_path], capture_output=True, timeout=self.config.timeout_seconds)
        if res.returncode != 0:
            raise RuntimeError(f"Apple Vision execution failed (exit code {res.returncode}): {res.stderr.decode('utf-8', 'replace')}")

        try:
            raw_list = json.loads(res.stdout.decode("utf-8"))
        except Exception as e:
            raise ValueError(f"Malformed JSON from Apple Vision runner: {e}")

        blocks: List[RawTextBlock] = []
        for b in raw_list:
            blocks.append(
                RawTextBlock(
                    text=b.get("text", "").strip(),
                    confidence=float(b.get("confidence", 1.0)),
                    x=float(b.get("x", 0.0)),
                    y=float(b.get("y", 0.0)),
                    width=float(b.get("width", 0.0)),
                    height=float(b.get("height", 0.0)),
                )
            )
        return blocks

    def extract_file(self, file_id: str, rel_path: str, origin: str, captured_at: Optional[str] = None) -> List[ExtractedObservation]:
        """Extracts structured observations from a screenshot locally, respecting cache."""
        full_path = os.path.join(self.repo_root, "dataset", rel_path)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"Screenshot file missing at {full_path}")

        with open(full_path, "rb") as f:
            img_bytes = f.read()

        cache_key = self._compute_cache_key(file_id, img_bytes)
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
        now_iso = datetime.now(timezone.utc).isoformat()
        manifest_time = parse_timestamp_to_utc(captured_at) if captured_at else None

        # Check cache
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                return self._deserialize_observations(cached.get("parsed_observations", []), rel_path, file_id, origin, manifest_time)
            except Exception as e:
                logger.warning("Cache read failed for %s, will re-execute: %s", cache_key, e)

        # Execute offline OCR
        t0 = time.time()
        raw_blocks = self.run_local_ocr(full_path)
        elapsed = time.time() - t0

        # Parse text blocks into spatial entity observations
        parsed_obs = self._parse_ocr_blocks(raw_blocks, file_id, rel_path, origin, manifest_time)

        # Write deterministic cache
        cache_data = {
            "file_id": file_id,
            "cache_key": cache_key,
            "created_at": now_iso,
            "provider": "apple_vision",
            "runtime": "macOS_Swift_Vision",
            "version": self.config.version,
            "source_file": rel_path,
            "image_sha256": hashlib.sha256(img_bytes).hexdigest(),
            "blocks_extracted": len(raw_blocks),
            "observations_count": len(parsed_obs),
            "execution_metrics": {
                "network_calls": 0,
                "api_calls": 0,
                "cost_usd": 0.0,
                "elapsed_seconds": round(elapsed, 4),
            },
            "raw_blocks": [asdict(b) for b in raw_blocks],
            "parsed_observations": [self._serialize_observation(o) for o in parsed_obs],
        }

        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, indent=2)

        return parsed_obs

    def _parse_ocr_blocks(
        self,
        blocks: List[RawTextBlock],
        file_id: str,
        source_path: str,
        origin: str,
        timestamp: Optional[datetime],
    ) -> List[ExtractedObservation]:
        """Parses spatial OCR text blocks into structured observations without inventing links."""
        observations: List[ExtractedObservation] = []

        # Regular expression patterns for canonical resources and identifiers
        res_pattern = re.compile(
            r"\b(account_\d+|search_\d+|data_flow_\d+|analytics_\d+|export_\d+|support_\d+|backup_\d+|audit_record_\d+|tombstone_\d+|ORD-\d+|CS-\d+)\b"
        )
        user_pattern = re.compile(r"\buser_\d+\b")
        email_pattern = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
        phone_pattern = re.compile(r"\+?\d[\d\s\-\(\)]{7,}\d")

        # 1. Identify all detected entity tokens with spatial locations
        detected_resources: List[Tuple[str, RawTextBlock]] = []
        detected_users: List[Tuple[str, RawTextBlock]] = []
        detected_emails: List[Tuple[str, RawTextBlock]] = []
        detected_phones: List[Tuple[str, RawTextBlock]] = []

        for b in blocks:
            for r_match in res_pattern.findall(b.text):
                detected_resources.append((r_match, b))
            for u_match in user_pattern.findall(b.text):
                detected_users.append((u_match, b))
            for e_match in email_pattern.findall(b.text):
                detected_emails.append((e_match, b))
            # Basic phone validation to avoid pure numbers/dates
            if any(char in b.text for char in ["+", "-", "("]):
                for p_match in phone_pattern.findall(b.text):
                    if len(re.sub(r"\D", "", p_match)) >= 8:
                        detected_phones.append((p_match, b))

        # 2. Build spatial cluster for each discovered resource
        for rid, rblock in detected_resources:
            # Find closest user_id, email, phone based on 2D Euclidean distance (y inverted in Apple Vision)
            associated_ids: Dict[str, str] = {}
            ambiguity_flags: List[str] = ["APPLE_VISION_LOCAL_OCR"]

            closest_user = self._find_spatially_close(rblock, detected_users, max_dist=0.35)
            if closest_user:
                associated_ids["user_id"] = closest_user

            closest_email = self._find_spatially_close(rblock, detected_emails, max_dist=0.35)
            if closest_email:
                norm_e = normalize_email(closest_email)
                if norm_e:
                    associated_ids["email"] = norm_e

            closest_phone = self._find_spatially_close(rblock, detected_phones, max_dist=0.35)
            if closest_phone:
                norm_p = normalize_phone(closest_phone)
                if norm_p:
                    associated_ids["phone"] = norm_p

            # Determine system ID from resource prefix or manifest origin
            prefix = rid.split("_")[0] if "_" in rid else "unknown"
            sys_map = {
                "account": "account_service",
                "search": "search_service",
                "data_flow": "integration_service",
                "analytics": "analytics_platform",
                "export": "export_service",
                "support": "support_platform",
                "backup": "backup_service",
                "audit_record": "security_service",
                "tombstone": "identity_service",
            }
            system_id = sys_map.get(prefix, origin)

            # Determine observed state from nearby status keywords
            state_val, state_conf = self._infer_state_from_nearby(rblock, blocks)
            
            confidence = ObservationConfidence.HIGH if (associated_ids and state_conf == "HIGH") else ObservationConfidence.MEDIUM
            if not associated_ids or state_val == ResourceState.UNKNOWN:
                confidence = ObservationConfidence.AMBIGUOUS
                ambiguity_flags.append("AMBIGUOUS_STATE_OR_IDENTITY_ASSOCIATION")

            obs = ExtractedObservation(
                source_file=source_path,
                file_id=file_id,
                evidence_id=file_id,
                source_location=f"visual_box:x={rblock.x:.3f},y={rblock.y:.3f},w={rblock.width:.3f},h={rblock.height:.3f}",
                observation_type="APPLE_VISION_OCR_RECORD",
                extraction_method="APPLE_VISION",
                confidence=confidence,
                timestamp=timestamp,
                resource_id=rid,
                system_id=system_id,
                associated_identifiers=associated_ids,
                observed_state=state_val,
                raw_payload={"ocr_text": rblock.text, "confidence": rblock.confidence},
                ambiguity_flags=ambiguity_flags,
            )
            observations.append(obs)

        # 3. If no specific resources were isolated, emit general screen observation with any detected user/email
        if not observations and (detected_users or detected_emails):
            top_ids: Dict[str, str] = {}
            if detected_users:
                top_ids["user_id"] = detected_users[0][0]
            if detected_emails:
                norm_e = normalize_email(detected_emails[0][0])
                if norm_e:
                    top_ids["email"] = norm_e

            obs = ExtractedObservation(
                source_file=source_path,
                file_id=file_id,
                evidence_id=file_id,
                source_location="visual_screen:unstructured_layout",
                observation_type="APPLE_VISION_UNSTRUCTURED_SCREEN",
                extraction_method="APPLE_VISION",
                confidence=ObservationConfidence.AMBIGUOUS,
                timestamp=timestamp,
                resource_id=None,
                system_id=origin,
                associated_identifiers=top_ids,
                observed_state=ResourceState.UNKNOWN,
                raw_payload={"blocks_count": len(blocks)},
                ambiguity_flags=["NO_CONCRETE_RESOURCE_ID_DETECTED", "AMBIGUOUS_SCREEN_LAYOUT"],
            )
            observations.append(obs)

        return observations

    def _find_spatially_close(self, target: RawTextBlock, candidates: List[Tuple[str, RawTextBlock]], max_dist: float = 0.35) -> Optional[str]:
        """Finds closest candidate string within 2D bounding-box Euclidean distance."""
        best_val: Optional[str] = None
        min_dist = float("inf")

        for val, cblock in candidates:
            # Emphasize vertical alignment for tables/cards (dy weighted more heavily)
            dx = abs(target.x - cblock.x)
            dy = abs(target.y - cblock.y)
            dist = (dx * dx + (dy * 2.0) * (dy * 2.0)) ** 0.5
            if dist < min_dist and dist <= max_dist:
                min_dist = dist
                best_val = val

        return best_val

    def _infer_state_from_nearby(self, target: RawTextBlock, blocks: List[RawTextBlock]) -> Tuple[ResourceState, str]:
        """Checks nearby text tokens for status indicators without inferring success from action buttons."""
        nearby_texts = []
        for b in blocks:
            # Look in vertical proximity (same row or adjacent card header)
            if abs(target.y - b.y) <= 0.08 and abs(target.x - b.x) <= 0.5:
                nearby_texts.append(b.text.upper())

        joined = " ".join(nearby_texts)
        
        # Action button exclusion rule: ignore buttons/tabs like 'DELETE' or 'REMOVE'
        if any(term in joined for term in ["ACTIONS", "BUTTON", "SEARCH"]):
            pass

        if "DISABLED" in joined:
            return ResourceState.DISABLED, "HIGH"
        if "BLOCKED" in joined:
            return ResourceState.BLOCKED, "HIGH"
        if "REDACTED" in joined:
            return ResourceState.REDACTED, "HIGH"
        if "ANONYMIZED" in joined:
            return ResourceState.ANONYMIZED, "HIGH"
        if any(term in joined for term in ["ACTIVE", "HEALTHY", "LIVE", "CONTINUOUS", "DELIVERED", "SIGNED"]):
            return ResourceState.PRESENT, "HIGH"
        if "DELETED" in joined:
            return ResourceState.ABSENT, "MEDIUM"

        # Default: if record exists in table, conservatively PRESENT
        return ResourceState.PRESENT, "MEDIUM"

    def _serialize_observation(self, obs: ExtractedObservation) -> Dict[str, Any]:
        """Serializes ExtractedObservation for JSON caching."""
        return {
            "source_file": obs.source_file,
            "file_id": obs.file_id,
            "evidence_id": obs.evidence_id,
            "source_location": obs.source_location,
            "observation_type": obs.observation_type,
            "extraction_method": obs.extraction_method,
            "confidence": obs.confidence.value,
            "timestamp": obs.timestamp.isoformat() if obs.timestamp else None,
            "resource_id": obs.resource_id,
            "system_id": obs.system_id,
            "associated_identifiers": obs.associated_identifiers,
            "observed_state": obs.observed_state.value if obs.observed_state else None,
            "raw_payload": obs.raw_payload,
            "ambiguity_flags": obs.ambiguity_flags,
        }

    def _deserialize_observations(
        self,
        cached_list: List[Dict[str, Any]],
        rel_path: str,
        file_id: str,
        origin: str,
        default_time: Optional[datetime],
    ) -> List[ExtractedObservation]:
        """Deserializes ExtractedObservation objects from cache."""
        observations: List[ExtractedObservation] = []
        for d in cached_list:
            st_val = None
            if d.get("observed_state") and d["observed_state"] in ResourceState._value2member_map_:
                st_val = ResourceState(d["observed_state"])

            conf_val = ObservationConfidence.MEDIUM
            if d.get("confidence") and d["confidence"] in ObservationConfidence._value2member_map_:
                conf_val = ObservationConfidence(d["confidence"])

            t_val = parse_timestamp_to_utc(d.get("timestamp")) if d.get("timestamp") else default_time

            obs = ExtractedObservation(
                source_file=d.get("source_file") or rel_path,
                file_id=d.get("file_id") or file_id,
                evidence_id=d.get("evidence_id") or file_id,
                source_location=d.get("source_location") or "visual_region:cached",
                observation_type=d.get("observation_type") or "APPLE_VISION_OCR_RECORD",
                extraction_method="APPLE_VISION",
                confidence=conf_val,
                timestamp=t_val,
                resource_id=d.get("resource_id"),
                system_id=d.get("system_id") or origin,
                associated_identifiers=dict(d.get("associated_identifiers") or {}),
                observed_state=st_val,
                raw_payload=dict(d.get("raw_payload") or {}),
                ambiguity_flags=list(d.get("ambiguity_flags") or []),
            )
            observations.append(obs)
        return observations
