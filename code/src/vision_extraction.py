"""code/src/vision_extraction.py

Controlled Gemini Multimodal Vision Extraction Adapter for HackerRank Orchestrate: Ghost Data Still Exists.

Extracts structured, provenance-backed observations from administrative console screenshots:
- Resolves verified image inventory from dataset/evidence_files.csv.
- Enforces explicit configuration, model specification, and feature flagging.
- Strictly separates direct visual facts from semantic interpretations.
- Caches results by image SHA-256, provider, model identifier, and prompt version.
- Tracks API token usage, latencies, request counts, and costs without leaking secrets.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import logging
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple
import urllib.error
import urllib.request

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

logger = logging.getLogger("nulltrace.vision_extraction")


def load_env_file(env_path: Optional[str] = None) -> None:
    """Loads environment variables from an uncommitted .env file if present, without logging values."""
    if env_path is None:
        env_path = os.path.join(_repo_root, ".env")
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("\"'")
                    if k and k not in os.environ:
                        os.environ[k] = v
    except Exception as e:
        logger.warning("Could not read .env file: %s", type(e).__name__)


@dataclass
class VisionConfig:
    """Configuration for controlled Gemini vision extraction."""
    provider: str = "gemini"
    model_id: str = "gemini-3.5-flash"
    api_key_env_var: str = "GEMINI_API_KEY"
    enabled: bool = False
    timeout_seconds: float = 30.0
    max_retries: int = 3
    cache_dir: str = "build/cache/vision"
    max_output_tokens: int = 2048
    prompt_version: str = "v1.0"
    api_base_url: str = "https://generativelanguage.googleapis.com/v1beta"

    @classmethod
    def from_env(cls, repo_root: Optional[str] = None) -> "VisionConfig":
        """Constructs config from environment variables, defaulting to disabled for safety."""
        load_env_file(os.path.join(repo_root or _repo_root, ".env"))
        
        enabled_val = os.environ.get("ENABLE_GEMINI_VISION", "").lower() in ("1", "true", "yes")
        model_val = os.environ.get("GEMINI_VISION_MODEL", "gemini-3.5-flash").strip()
        cache_dir_val = os.environ.get("GEMINI_CACHE_DIR", "build/cache/vision").strip()
        
        return cls(
            model_id=model_val or "gemini-3.5-flash",
            enabled=enabled_val,
            cache_dir=cache_dir_val or "build/cache/vision",
        )


@dataclass
class UsageRecord:
    """Usage accounting ledger entry for a single model interaction or cache retrieval."""
    timestamp: str
    provider: str
    model: str
    file_id: str
    cache_hit: bool
    request_count: int
    prompt_tokens: Optional[int] = None
    candidates_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    estimated_cost_usd: Optional[float] = None
    retries: int = 0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def get_verified_image_inventory(repo_root: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """Resolves and validates all IMAGE_ONLY evidence files from evidence_files.csv.
    
    Returns mapping of file_id -> metadata dictionary.
    Raises FileNotFoundError if evidence_files.csv or any referenced image is missing.
    """
    root = repo_root or _repo_root
    manifest_path = os.path.join(root, "dataset", "evidence_files.csv")
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"Evidence manifest missing at {manifest_path}")

    import csv
    verified_images: Dict[str, Dict[str, Any]] = {}
    
    with open(manifest_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            file_id = row.get("file_id", "").strip()
            rel_path = row.get("file_path", "").strip()
            
            # Identify image files by extension or explicit source type
            is_image = rel_path.lower().endswith((".png", ".jpg", ".jpeg", ".webp")) or "image" in row.get("source_type", "").lower()
            if not is_image:
                continue

            resolved_path = os.path.join(root, "dataset", rel_path)
            if not os.path.exists(resolved_path):
                raise FileNotFoundError(
                    f"Evidence file {file_id} references non-existent image path: {resolved_path}"
                )
            
            size_bytes = os.path.getsize(resolved_path)
            if size_bytes == 0:
                raise ValueError(f"Evidence image {file_id} at {resolved_path} is 0 bytes")

            verified_images[file_id] = {
                "file_id": file_id,
                "file_path": rel_path,
                "resolved_path": resolved_path,
                "origin": row.get("origin", "").strip(),
                "captured_at": row.get("captured_at", "").strip(),
                "size_bytes": size_bytes,
            }

    return verified_images


VISION_EXTRACTION_SYSTEM_PROMPT = """You are an evidence extraction assistant auditing platform data-deletion compliance.
Analyze the provided administrative console screenshot with strict factual discipline.

CRITICAL EXTRACTION RULES:
1. Extract ONLY information that is factually and directly visible in the image.
2. DO NOT hallucinate, infer, or assume identifiers or records that are not visible.
3. Distinguish direct visual facts (exact text, table cells, form values) from interpretations.
4. Record exact resource identifiers (e.g. account_5762, support_9538, ORD-20265762, CS-8538, user_11).
5. Extract all visible personal identifiers: user_id, email, phone, full name, street address.
6. For status labels, record the exact visible label (e.g. 'Active', 'Delivered', 'Silver') and map to standard state:
   - 'PRESENT': record exists in system.
   - 'ABSENT': record verified as deleted/not found.
   - 'REDACTED': fields are masked, hashed, or blanked out.
   - 'ANONYMIZED': irreversible pseudonymization observed.
   - 'ACTIVE' / 'DISABLED': for services, toggles, or data pipelines.
   - 'BLOCKED': for restore or backup access.
   - null: if state cannot be determined from visible evidence.
7. If any region is blurry, truncated, or unreadable, record it in 'unreadable_regions' and mark confidence 'AMBIGUOUS' or 'UNCERTAIN'.
8. Return strictly valid JSON adhering to the specified schema.
"""


class GeminiVisionExtractor:
    """Controlled vision extraction engine with caching, usage tracking, and provenance recording."""

    def __init__(self, config: Optional[VisionConfig] = None, repo_root: Optional[str] = None):
        self.repo_root = repo_root or _repo_root
        self.config = config or VisionConfig.from_env(self.repo_root)
        self.cache_dir = os.path.join(self.repo_root, self.config.cache_dir)
        os.makedirs(self.cache_dir, exist_ok=True)
        self.verified_inventory = get_verified_image_inventory(self.repo_root)
        self.usage_ledger_path = os.path.join(self.cache_dir, "usage_ledger.json")

    def _get_api_key(self) -> Optional[str]:
        """Retrieves API key from environment, never storing or logging it."""
        load_env_file(os.path.join(self.repo_root, ".env"))
        return os.environ.get(self.config.api_key_env_var)

    def _compute_cache_key(self, file_id: str, image_bytes: bytes) -> str:
        """Computes deterministic cache key from image sha256, model_id, and prompt version."""
        img_sha = hashlib.sha256(image_bytes).hexdigest()
        clean_model = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", self.config.model_id)
        return f"{file_id}_{img_sha[:16]}_{clean_model}_{self.config.prompt_version}"

    def _record_usage(self, record: UsageRecord) -> None:
        """Appends a usage record to the persistent usage ledger."""
        ledger: List[Dict[str, Any]] = []
        if os.path.exists(self.usage_ledger_path):
            try:
                with open(self.usage_ledger_path, "r", encoding="utf-8") as f:
                    ledger = json.load(f)
            except Exception:
                ledger = []
        ledger.append(record.to_dict())
        with open(self.usage_ledger_path, "w", encoding="utf-8") as f:
            json.dump(ledger, f, indent=2)

    def _estimate_cost(self, prompt_tokens: Optional[int], candidates_tokens: Optional[int]) -> Optional[float]:
        """Calculates estimated USD cost for Gemini 3.5 Flash based on token counts."""
        if prompt_tokens is None or candidates_tokens is None:
            return None
        # Gemini 3.5 Flash rate: $0.075 per 1M input tokens, $0.30 per 1M output tokens
        input_cost = (prompt_tokens / 1_000_000.0) * 0.075
        output_cost = (candidates_tokens / 1_000_000.0) * 0.30
        return round(input_cost + output_cost, 6)

    def _execute_api_call(self, image_bytes: bytes, file_id: str) -> Tuple[Dict[str, Any], Dict[str, Any], int]:
        """Executes a single multimodal API call to Gemini with timeout and retries."""
        import base64

        api_key = self._get_api_key()
        if not api_key:
            raise ValueError(f"Missing API key in environment variable {self.config.api_key_env_var}")

        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        
        # Build strict JSON schema instruction
        prompt_text = (
            f"{VISION_EXTRACTION_SYSTEM_PROMPT}\n\n"
            f"FILE_ID: {file_id}\n"
            "Return JSON matching this exact structure:\n"
            "{\n"
            '  "file_id": "...",\n'
            '  "screen_title": "...",\n'
            '  "system_id": "...",\n'
            '  "ui_timestamp": "...",\n'
            '  "records": [\n'
            "    {\n"
            '      "visual_region": "...",\n'
            '      "resource_id": "...",\n'
            '      "system_id": "...",\n'
            '      "identifiers": {\n'
            '        "user_id": "...",\n'
            '        "email": "...",\n'
            '        "phone": "...",\n'
            '        "name": "...",\n'
            '        "address": "..."\n'
            "      },\n"
            '      "raw_status_label": "...",\n'
            '      "observed_state": "PRESENT | ABSENT | REDACTED | ANONYMIZED | ACTIVE | DISABLED | BLOCKED",\n'
            '      "observation_type": "...",\n'
            '      "is_direct_observation": true,\n'
            '      "visual_evidence_notes": "...",\n'
            '      "confidence": "HIGH | MEDIUM | UNCERTAIN | AMBIGUOUS",\n'
            '      "ambiguity_flags": []\n'
            "    }\n"
            "  ],\n"
            '  "unreadable_regions": []\n'
            "}"
        )

        model_path = self.config.model_id
        if not model_path.startswith("models/"):
            model_path = f"models/{model_path}"

        url = f"{self.config.api_base_url}/{model_path}:generateContent?key={api_key}"

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt_text},
                        {"inline_data": {"mime_type": "image/png", "data": b64_image}},
                    ]
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.0,
                "max_output_tokens": 4096,
            },
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        last_error = None
        for attempt in range(self.config.max_retries):
            try:
                with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    candidates = resp_data.get("candidates", [])
                    if not candidates:
                        raise ValueError("Gemini API returned no candidates in response")
                    text_content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    
                    # Clean markdown code blocks if present
                    text_content = text_content.strip()
                    if text_content.startswith("```"):
                        text_content = re.sub(r"^```(?:json)?\s*", "", text_content)
                        text_content = re.sub(r"\s*```$", "", text_content)
                    
                    parsed_json = json.loads(text_content)
                    usage_metadata = resp_data.get("usageMetadata", {})
                    return parsed_json, usage_metadata, attempt
            except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError, ValueError) as e:
                last_error = e
                logger.warning("Gemini API call attempt %d failed: %s", attempt + 1, e)
                time.sleep(1.0 * (attempt + 1))

        raise RuntimeError(f"Gemini API request failed after {self.config.max_retries} attempts: {type(last_error).__name__} ({last_error})")

    def extract_file(self, file_id: str) -> List[ExtractedObservation]:
        """Extracts structured observations from a verified image screenshot.
        
        If caching is active, returns cached observations immediately.
        If vision extraction is disabled, returns an empty list without calling the API.
        """
        if file_id not in self.verified_inventory:
            raise KeyError(f"Image {file_id} not in verified image inventory")

        meta = self.verified_inventory[file_id]
        img_path = meta["resolved_path"]
        
        with open(img_path, "rb") as f:
            img_bytes = f.read()

        cache_key = self._compute_cache_key(file_id, img_bytes)
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
        now_iso = datetime.now(timezone.utc).isoformat()

        # Check Cache
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                
                # Record cache hit in usage ledger
                u_meta = cached_data.get("usage_metadata", {})
                self._record_usage(
                    UsageRecord(
                        timestamp=now_iso,
                        provider=self.config.provider,
                        model=self.config.model_id,
                        file_id=file_id,
                        cache_hit=True,
                        request_count=0,
                        prompt_tokens=u_meta.get("promptTokenCount"),
                        candidates_tokens=u_meta.get("candidatesTokenCount"),
                        total_tokens=u_meta.get("totalTokenCount"),
                        estimated_cost_usd=0.0,
                    )
                )
                return self._parse_structured_response(file_id, meta, cached_data.get("model_output", {}))
            except Exception as e:
                logger.warning("Cache read failed for %s, will re-execute: %s", cache_key, e)

        # Feature Flag Protection
        if not self.config.enabled:
            logger.info("Vision extraction disabled for %s (ENABLE_GEMINI_VISION=false)", file_id)
            return []

        # Execute API Call
        try:
            model_output, usage_meta, retries = self._execute_api_call(img_bytes, file_id)
        except Exception as e:
            self._record_usage(
                UsageRecord(
                    timestamp=now_iso,
                    provider=self.config.provider,
                    model=self.config.model_id,
                    file_id=file_id,
                    cache_hit=False,
                    request_count=1,
                    retries=self.config.max_retries,
                    error=str(type(e).__name__),
                )
            )
            raise

        # Save Cache
        cache_payload = {
            "file_id": file_id,
            "cache_key": cache_key,
            "created_at": now_iso,
            "provider": self.config.provider,
            "model_id": self.config.model_id,
            "prompt_version": self.config.prompt_version,
            "usage_metadata": usage_meta,
            "model_output": model_output,
        }
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_payload, f, indent=2)

        p_tokens = usage_meta.get("promptTokenCount")
        c_tokens = usage_meta.get("candidatesTokenCount")
        t_tokens = usage_meta.get("totalTokenCount")
        cost = self._estimate_cost(p_tokens, c_tokens)

        # Record API Miss in Ledger
        self._record_usage(
            UsageRecord(
                timestamp=now_iso,
                provider=self.config.provider,
                model=self.config.model_id,
                file_id=file_id,
                cache_hit=False,
                request_count=1,
                prompt_tokens=p_tokens,
                candidates_tokens=c_tokens,
                total_tokens=t_tokens,
                estimated_cost_usd=cost,
                retries=retries,
            )
        )

        return self._parse_structured_response(file_id, meta, model_output)

    def _parse_structured_response(
        self, file_id: str, meta: Dict[str, Any], model_output: Dict[str, Any]
    ) -> List[ExtractedObservation]:
        """Maps model output to standardized ExtractedObservation objects with strict validation."""
        observations: List[ExtractedObservation] = []
        captured_str = meta.get("captured_at")
        manifest_time = parse_timestamp_to_utc(captured_str) if captured_str else None

        # Schema 1: Direct 'records' list
        records = model_output.get("records")
        if isinstance(records, list) and records:
            for idx, rec in enumerate(records):
                if not isinstance(rec, dict):
                    continue

                raw_region = rec.get("visual_region") or f"region_{idx+1}"
                raw_res = rec.get("resource_id")
                resource_id = str(raw_res).strip() if raw_res else None
                system_id = rec.get("system_id") or meta.get("origin")
                
                raw_state = str(rec.get("observed_state", "")).upper()
                state_val: Optional[ResourceState] = None
                if raw_state in ResourceState._value2member_map_:
                    state_val = ResourceState(raw_state)

                raw_ids = rec.get("identifiers") or {}
                norm_ids: Dict[str, str] = {}
                if isinstance(raw_ids, dict):
                    for k, v in raw_ids.items():
                        if not v:
                            continue
                        v_str = str(v).strip()
                        if k.lower() in ("email", "mail"):
                            norm_e = normalize_email(v_str)
                            if norm_e:
                                norm_ids["email"] = norm_e
                        elif k.lower() in ("phone", "tel"):
                            norm_p = normalize_phone(v_str)
                            if norm_p:
                                norm_ids["phone"] = norm_p
                        elif k.lower() in ("user_id", "subject_id"):
                            norm_ids["user_id"] = v_str
                        elif k.lower() in ("name", "full_name"):
                            norm_ids["name"] = v_str
                        else:
                            norm_ids[k.lower()] = v_str

                raw_conf = str(rec.get("confidence", "MEDIUM")).upper()
                if raw_conf == "HIGH":
                    confidence = ObservationConfidence.HIGH
                elif raw_conf in ("UNCERTAIN", "AMBIGUOUS"):
                    confidence = ObservationConfidence.AMBIGUOUS
                else:
                    confidence = ObservationConfidence.MEDIUM

                ambiguity_flags = list(rec.get("ambiguity_flags") or [])
                if not rec.get("is_direct_observation", True):
                    ambiguity_flags.append("INFERRED_INTERPRETATION")

                obs = ExtractedObservation(
                    source_file=meta["file_path"],
                    file_id=file_id,
                    evidence_id=file_id,
                    source_location=f"visual_region:{raw_region}",
                    observation_type=rec.get("observation_type") or "VISION_RECORD_OBSERVATION",
                    extraction_method="GEMINI_VISION",
                    confidence=confidence,
                    timestamp=manifest_time,
                    resource_id=resource_id,
                    system_id=system_id,
                    associated_identifiers=norm_ids,
                    observed_state=state_val,
                    raw_payload=rec,
                    ambiguity_flags=ambiguity_flags,
                )
                observations.append(obs)
            return observations

        # Schema 2: Hierarchical dashboard schema (customer_profile, orders, support)
        profile = model_output.get("customer_profile") or model_output.get("subject_identifiers") or {}
        norm_ids: Dict[str, str] = {}
        if isinstance(profile, dict):
            for k, v in profile.items():
                if not v or isinstance(v, (dict, list)):
                    continue
                v_str = str(v).strip()
                if k.lower() in ("email", "mail"):
                    norm_e = normalize_email(v_str)
                    if norm_e:
                        norm_ids["email"] = norm_e
                elif k.lower() in ("phone", "tel"):
                    norm_p = normalize_phone(v_str)
                    if norm_p:
                        norm_ids["phone"] = norm_p
                elif k.lower() in ("user_id", "subject_id"):
                    norm_ids["user_id"] = v_str
                elif k.lower() in ("name", "full_name"):
                    norm_ids["name"] = v_str
                elif k.lower() in ("default_address", "street_address", "address"):
                    norm_ids["address"] = v_str

        # 1. Main account record observation
        account_id = None
        if isinstance(profile, dict):
            account_id = profile.get("account_id") or profile.get("resource_id")
        
        if account_id or norm_ids:
            obs = ExtractedObservation(
                source_file=meta["file_path"],
                file_id=file_id,
                evidence_id=file_id,
                source_location="visual_region:Customer_Profile_Card",
                observation_type="ACCOUNT_RECORD",
                extraction_method="GEMINI_VISION",
                confidence=ObservationConfidence.HIGH,
                timestamp=manifest_time,
                resource_id=str(account_id).strip() if account_id else None,
                system_id=meta.get("origin") or "account_admin_portal",
                associated_identifiers=dict(norm_ids),
                observed_state=ResourceState.PRESENT,
                raw_payload={"profile": profile},
                ambiguity_flags=[],
            )
            observations.append(obs)

        # 2. Associated orders observations
        orders = model_output.get("orders") or []
        if isinstance(orders, list):
            for idx, ord_item in enumerate(orders):
                if not isinstance(ord_item, dict):
                    continue
                ord_id = ord_item.get("order_id")
                if ord_id:
                    status_dict = ord_item.get("status") if isinstance(ord_item.get("status"), dict) else {}
                    mapped_st = status_dict.get("mapped_state") or "PRESENT"
                    st_val = ResourceState(mapped_st) if mapped_st in ResourceState._value2member_map_ else ResourceState.PRESENT

                    obs = ExtractedObservation(
                        source_file=meta["file_path"],
                        file_id=file_id,
                        evidence_id=file_id,
                        source_location=f"visual_region:Orders_Table_Row_{idx+1}",
                        observation_type="ORDER_RECORD",
                        extraction_method="GEMINI_VISION",
                        confidence=ObservationConfidence.HIGH,
                        timestamp=manifest_time,
                        resource_id=str(ord_id).strip(),
                        system_id="order_service",
                        associated_identifiers=dict(norm_ids),
                        observed_state=st_val,
                        raw_payload=ord_item,
                        ambiguity_flags=[],
                    )
                    observations.append(obs)

        # 3. Support references
        support_ids = []
        if isinstance(profile, dict):
            raw_supp = profile.get("support_identifiers")
            if isinstance(raw_supp, list):
                support_ids.extend([str(s).strip() for s in raw_supp if s])
            elif isinstance(raw_supp, str):
                support_ids.extend([s.strip() for s in raw_supp.split("·") if s.strip()])

        for supp_id in support_ids:
            obs = ExtractedObservation(
                source_file=meta["file_path"],
                file_id=file_id,
                evidence_id=file_id,
                source_location="visual_region:Customer_Support_Sidebar",
                observation_type="SUPPORT_RECORD",
                extraction_method="GEMINI_VISION",
                confidence=ObservationConfidence.HIGH,
                timestamp=manifest_time,
                resource_id=supp_id,
                system_id="support_platform",
                associated_identifiers=dict(norm_ids),
                observed_state=ResourceState.PRESENT,
                raw_payload={"support_id": supp_id},
                ambiguity_flags=[],
            )
            observations.append(obs)

        return observations

