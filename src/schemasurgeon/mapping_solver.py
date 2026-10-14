"""Evidence-based Mapping Solver with hard safety gates."""

import re
from typing import Any, Dict, List, Optional, Tuple
from schemasurgeon.models import FieldMapping
from schemasurgeon.schema_diff import SchemaDiffResult, PropertyMeta


_STOPWORDS = {"of", "the", "a", "an", "is", "in", "to", "for", "with", "by", "from", "on", "at"}


def _tokenize(text: str) -> set[str]:
    """Extracts lower-cased alphanumeric tokens from camelCase, snake_case or descriptions, filtering stopwords."""
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", text)
    s2 = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1)
    tokens = set(re.findall(r"[a-z0-9]+", s2.lower()))
    filtered = tokens - _STOPWORDS
    return filtered if filtered else tokens


def compute_token_similarity(text1: str, text2: str) -> float:
    """Computes Jaccard similarity between two token sets."""
    t1 = _tokenize(text1)
    t2 = _tokenize(text2)
    if not t1 or not t2:
        return 0.0
    intersection = t1.intersection(t2)
    union = t1.union(t2)
    return len(intersection) / len(union)


def is_safe_integer_conversion(value: Any) -> bool:
    """
    Checks if a string representation can be converted to integer without information loss.
    '123' -> 123 is SAFE.
    '00123' -> 123 is UNSAFE (loses leading zeros).
    'abc' -> UNSAFE.
    """
    if isinstance(value, int):
        return True
    if not isinstance(value, str):
        return False
    value = value.strip()
    if not value.isdigit():
        return False
    # Check leading zero preservation: int('00123') -> 123 -> str(123) == '123' != '00123'
    try:
        int_val = int(value)
        return str(int_val) == value
    except ValueError:
        return False


def is_security_sensitive(field_name: str) -> bool:
    """Checks if field name looks like a credential or security-sensitive property."""
    sensitive_tokens = {"password", "secret", "token", "key", "auth", "credential", "api_key", "bearer"}
    tokens = _tokenize(field_name)
    return bool(tokens.intersection(sensitive_tokens))


class MappingSolver:
    """Solves field mappings from schema diff with hard safety gates."""

    def __init__(self, min_score: float = 0.50, unique_match_margin: float = 0.15):
        self.min_score = min_score
        self.unique_match_margin = unique_match_margin

    def solve(
        self,
        diff: SchemaDiffResult,
        original_args: Dict[str, Any],
        trusted_headers: Optional[Dict[str, str]] = None,
    ) -> Tuple[List[FieldMapping], List[str], List[str]]:
        """
        Computes safe candidate field mappings.
        Returns: (approved_mappings, evidence_list, refusal_reasons)
        """
        mappings: List[FieldMapping] = []
        evidence: List[str] = []
        refusals: List[str] = []

        trusted_h = trusted_headers or {}

        # 1. Check for required headers
        for h_name in diff.new_headers:
            if h_name not in trusted_h:
                refusals.append(f"Missing authoritative value for required header '{h_name}'")

        # 2. Map removed/changed properties from old schema to new schema
        for src_path, src_meta in diff.old_properties.items():
            if is_security_sensitive(src_path):
                refusals.append(f"Security-sensitive field '{src_path}' cannot be automatically mapped")
                continue

            # If src_path is still present in new properties
            if src_path in diff.new_properties:
                tgt_meta = diff.new_properties[src_path]
                if src_meta.type != tgt_meta.type:
                    # Type conversion check
                    if src_meta.type == "string" and tgt_meta.type == "integer":
                        val = original_args.get(src_path)
                        if val is not None and not is_safe_integer_conversion(val):
                            refusals.append(
                                f"Unsafe type conversion: '{val}' loses leading zeros or information when converted to integer"
                            )
                        else:
                            mappings.append(FieldMapping(
                                source_path=src_path,
                                target_path=src_path,
                                transformation="coerce_int",
                                evidence=[f"Path unchanged, converted {src_meta.type} to {tgt_meta.type}"],
                                confidence=0.95,
                            ))
                            evidence.append(f"Type conversion {src_path}: string -> integer safely supported")
                    else:
                        mappings.append(FieldMapping(
                            source_path=src_path,
                            target_path=src_path,
                            transformation="identity",
                            evidence=[f"Path unchanged, types {src_meta.type} -> {tgt_meta.type}"],
                            confidence=0.80,
                        ))
                continue

            # src_path was removed or restructured, find candidate destinations
            candidate_scores: List[Tuple[str, PropertyMeta, float, List[str]]] = []

            for tgt_path, tgt_meta in diff.new_properties.items():
                if tgt_path in diff.old_properties:
                    continue  # already occupied by existing property

                if is_security_sensitive(tgt_path):
                    continue

                # Signal 1: Description-token similarity (0.50)
                desc_sim = compute_token_similarity(src_meta.description, tgt_meta.description)
                # Signal 2: Path-token overlap (0.30)
                name_sim = compute_token_similarity(src_meta.name, tgt_meta.name)
                path_sim = max(compute_token_similarity(src_path, tgt_path), name_sim)
                # Signal 3: Structural/type compatibility (0.20)
                is_nested = any(
                    n.get("source") == src_path and n.get("target") == tgt_path
                    for n in diff.nested_changes
                ) or (tgt_path.endswith(f".{src_meta.name}") or (tgt_path.endswith(".id") and "id" in src_meta.name))

                if is_nested:
                    type_compat = 1.0
                elif src_meta.type == tgt_meta.type:
                    type_compat = 1.0
                elif src_meta.type == "string" and tgt_meta.type == "integer":
                    type_compat = 0.8
                else:
                    type_compat = 0.2

                score = (0.50 * desc_sim) + (0.30 * path_sim) + (0.20 * type_compat)
                item_evidence = [
                    f"Description similarity: {desc_sim:.2f}",
                    f"Path similarity: {path_sim:.2f}",
                    f"Type compatibility: {type_compat:.2f}",
                ]
                candidate_scores.append((tgt_path, tgt_meta, score, item_evidence))

            if not candidate_scores:
                refusals.append(f"No candidate target field found for '{src_path}'")
                continue

            # Sort by score descending
            candidate_scores.sort(key=lambda x: x[2], reverse=True)
            top_tgt, top_meta, top_score, top_ev = candidate_scores[0]

            # Hard safety gate: Minimum confidence score
            if top_score < self.min_score:
                refusals.append(
                    f"Insufficient confidence score ({top_score:.2f} < {self.min_score}) for mapping '{src_path}' to '{top_tgt}'"
                )
                continue

            # Hard safety gate: Ambiguity check (margin between top 1 and top 2)
            if len(candidate_scores) > 1:
                second_tgt, _, second_score, _ = candidate_scores[1]
                diff_score = top_score - second_score
                if diff_score < self.unique_match_margin:
                    refusals.append(
                        f"Ambiguous mapping for '{src_path}': top candidate '{top_tgt}' ({top_score:.2f}) "
                        f"and second candidate '{second_tgt}' ({second_score:.2f}) differ by only {diff_score:.2f} (< {self.unique_match_margin})"
                    )
                    continue

            # Hard safety gate: Value check for type conversion
            transformation = "move"
            if src_meta.type == "string" and top_meta.type == "integer":
                val = original_args.get(src_path)
                if val is not None and not is_safe_integer_conversion(val):
                    refusals.append(
                        f"Unsafe type conversion: '{val}' loses leading zeros or information when converted to integer"
                    )
                    continue
                transformation = "coerce_int"

            mapping = FieldMapping(
                source_path=src_path,
                target_path=top_tgt,
                transformation=transformation,
                evidence=top_ev,
                confidence=top_score,
            )
            mappings.append(mapping)
            evidence.append(f"Mapped '{src_path}' -> '{top_tgt}' (score: {top_score:.2f}, transform: {transformation})")

        return mappings, evidence, refusals
