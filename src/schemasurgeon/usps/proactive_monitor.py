"""USP 1: Proactive Documentation-Based Adaptation."""

from typing import Any, Dict, List, Optional, Tuple
import httpx
from schemasurgeon.config import settings
from schemasurgeon.models import ToolContract, RepairCandidate
from schemasurgeon.registry import ToolRegistry, canonical_contract_hash
from schemasurgeon.schema_diff import diff_schemas
from schemasurgeon.mapping_solver import MappingSolver
from schemasurgeon.repair import RequestRepairEngine


class ProactiveMonitor:
    """Monitors OpenAPI contract documentation to detect and adapt to drift proactively."""

    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self.mapping_solver = MappingSolver(
            min_score=settings.min_confidence_score,
            unique_match_margin=settings.unique_match_margin,
        )
        self.repair_engine = RequestRepairEngine()

    async def check_for_drift(
        self,
        tool_name: str,
        trusted_headers: Optional[Dict[str, str]] = None,
    ) -> Tuple[bool, Optional[RepairCandidate], List[str]]:
        """
        Polls OpenAPI documentation, detects breaking changes vs active contract,
        and constructs a validated candidate repair BEFORE any runtime error occurs.
        Returns: (drift_detected, candidate, evidence_list)
        """
        active = self.registry.get_active(tool_name)
        if not active:
            return False, None, ["Tool not registered"]

        evidence: List[str] = []
        server_url = active.server_url

        # Check origin allowlist
        trusted = any(server_url.startswith(origin) for origin in settings.trusted_origins)
        if not trusted:
            return False, None, ["Server URL not in trusted origins allowlist"]

        openapi_url = f"{server_url.rstrip('/')}/openapi.json"
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(openapi_url)
                if resp.status_code != 200:
                    return False, None, [f"Failed to fetch OpenAPI: HTTP {resp.status_code}"]

                openapi_doc = resp.json()
        except Exception as e:
            return False, None, [f"Network exception fetching OpenAPI: {str(e)}"]

        # Parse target tool definition from OpenAPI
        paths = openapi_doc.get("paths", {})
        path_item = paths.get(active.path, {})
        op = path_item.get(active.method.lower(), {})
        if not op:
            return False, None, ["Tool path/method not found in OpenAPI"]

        req_body = op.get("requestBody", {})
        content = req_body.get("content", {})
        candidate_req = content.get("application/json", {}).get("schema")

        resp_200 = op.get("responses", {}).get("200", {})
        candidate_resp = resp_200.get("content", {}).get("application/json", {}).get("schema")

        # Required headers
        candidate_headers: Dict[str, str] = {}
        parameters = op.get("parameters", [])
        for p in parameters:
            if p.get("in") == "header" and p.get("required"):
                h_name = p.get("name")
                h_schema = p.get("schema", {})
                default_val = h_schema.get("default")
                if not default_val and "enum" in h_schema and h_schema["enum"]:
                    default_val = str(h_schema["enum"][0])
                candidate_headers[h_name] = str(default_val or "")

        if not candidate_req:
            return False, None, ["No request schema found in OpenAPI"]

        # Canonical hash check
        full_dict = {
            "method": active.method,
            "path": active.path,
            "request_schema": candidate_req,
            "response_schema": candidate_resp,
            "required_headers": candidate_headers,
        }
        new_hash = canonical_contract_hash(full_dict)

        if new_hash == active.contract_hash:
            return False, None, ["No contract change detected (hashes match)"]

        evidence.append("Proactive monitor detected OpenAPI contract hash mismatch")

        # Diff schemas
        active_resp = active.response_schema or {}
        diff = diff_schemas(
            old_req=active.request_schema,
            new_req=candidate_req,
            old_resp=active_resp,
            new_resp=candidate_resp,
            old_headers=active.required_headers,
            new_headers=candidate_headers,
        )

        trusted_h = trusted_headers or active.required_headers

        # Mapping solver using typical probe arguments
        probe_args = {"user_id": "123"}
        mappings, mapping_ev, refusals = self.mapping_solver.solve(
            diff=diff,
            original_args=probe_args,
            trusted_headers=trusted_h,
        )
        evidence.extend(mapping_ev)

        if refusals:
            evidence.append(f"Proactive adaptation refused: {'; '.join(refusals)}")
            return True, None, evidence

        candidate = self.repair_engine.build_candidate(
            tool_name=tool_name,
            current_version=active.version,
            diff=diff,
            mappings=mappings,
            original_args=probe_args,
            candidate_req_schema=candidate_req,
            candidate_resp_schema=candidate_resp or {},
            trusted_headers=trusted_h,
            evidence=evidence,
        )

        # Test candidate against sandbox mock API endpoint before promotion
        transformed_probe, req_headers = self.repair_engine.apply_adapter(
            probe_args, {}, candidate.request_adapter
        )

        test_url = f"{server_url.rstrip('/')}{active.path}"
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                probe_resp = await client.request(
                    method=active.method,
                    url=test_url,
                    json=transformed_probe,
                    headers=req_headers,
                )
                if probe_resp.status_code == 200:
                    evidence.append("Sandbox probe request succeeded against mock API (HTTP 200)")
                    candidate.confidence_score = 1.0
                    candidate.decision = "AUTO_REPAIR"
                else:
                    evidence.append(f"Sandbox probe returned HTTP {probe_resp.status_code}")
                    candidate.decision = "REQUIRES_APPROVAL"
        except Exception as e:
            evidence.append(f"Sandbox probe network exception: {str(e)}")

        return True, candidate, evidence
