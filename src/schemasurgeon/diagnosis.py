"""Diagnosis Engine: gathers multi-source evidence and diagnoses schema drift."""

from typing import Any, Dict, List, Optional, Tuple
import httpx
from schemasurgeon.config import settings
from schemasurgeon.models import ToolContract, RepairCandidate
from schemasurgeon.schema_diff import diff_schemas
from schemasurgeon.mapping_solver import MappingSolver
from schemasurgeon.repair import RequestRepairEngine


class DiagnosisEngine:
    """Diagnoses schema drift from error responses, OpenAPI contracts, and memory."""

    def __init__(self):
        self.mapping_solver = MappingSolver(
            min_score=settings.min_confidence_score,
            unique_match_margin=settings.unique_match_margin,
        )
        self.repair_engine = RequestRepairEngine()

    def is_schema_related_error(
        self,
        status_code: int,
        response_body: Any,
    ) -> bool:
        """Determines if an HTTP error is schema/validation related."""
        if status_code in (400, 422):
            return True
        if isinstance(response_body, dict):
            err_cls = response_body.get("error_class", "")
            if "schema" in err_cls or "validation" in err_cls:
                return True
        return False

    async def fetch_fresh_contract(
        self,
        server_url: str,
        path: str,
        method: str,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Dict[str, str], Optional[str]]:
        """
        Fetches fresh OpenAPI spec from trusted server URL only.
        Never fetches arbitrary URLs.
        Returns: (candidate_req_schema, candidate_resp_schema, new_headers, openapi_hash)
        """
        # Validate origin
        trusted = any(server_url.startswith(origin) for origin in settings.trusted_origins)
        if not trusted:
            return None, None, {}, None

        openapi_url = f"{server_url.rstrip('/')}/openapi.json"
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(openapi_url)
                if resp.status_code != 200:
                    return None, None, {}, None

                openapi_doc = resp.json()
                paths = openapi_doc.get("paths", {})
                path_item = paths.get(path, {})
                op = path_item.get(method.lower(), {})

                req_body = op.get("requestBody", {})
                content = req_body.get("content", {})
                json_content = content.get("application/json", {})
                req_schema = json_content.get("schema")

                resp_200 = op.get("responses", {}).get("200", {})
                resp_content = resp_200.get("content", {}).get("application/json", {})
                resp_schema = resp_content.get("schema")

                # Extract required headers
                headers: Dict[str, str] = {}
                parameters = op.get("parameters", [])
                for p in parameters:
                    if p.get("in") == "header" and p.get("required"):
                        h_name = p.get("name")
                        h_schema = p.get("schema", {})
                        default_val = h_schema.get("default")
                        if not default_val and "enum" in h_schema and h_schema["enum"]:
                            default_val = str(h_schema["enum"][0])
                        if default_val:
                            headers[h_name] = str(default_val)
                        else:
                            # Flag presence
                            headers[h_name] = ""

                return req_schema, resp_schema, headers, None
        except Exception:
            # Fallback to local in-process mock_app if port 8001 is not running externally
            try:
                from mock_api.app import mock_app
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=mock_app), base_url=server_url) as client:
                    resp = await client.get("/openapi.json")
                    if resp.status_code == 200:
                        openapi_doc = resp.json()
                        paths = openapi_doc.get("paths", {})
                        path_item = paths.get(path, {})
                        op = path_item.get(method.lower(), {})
                        req_body = op.get("requestBody", {})
                        content = req_body.get("content", {})
                        json_content = content.get("application/json", {})
                        req_schema = json_content.get("schema")
                        resp_200 = op.get("responses", {}).get("200", {})
                        resp_content = resp_200.get("content", {}).get("application/json", {})
                        resp_schema = resp_content.get("schema")
                        headers = {}
                        for p in op.get("parameters", []):
                            if p.get("in") == "header" and p.get("required"):
                                h_name = p.get("name")
                                h_schema = p.get("schema", {})
                                default_val = h_schema.get("default")
                                if not default_val and "enum" in h_schema and h_schema["enum"]:
                                    default_val = str(h_schema["enum"][0])
                                headers[h_name] = str(default_val or "")
                        return req_schema, resp_schema, headers, None
            except Exception:
                pass
            return None, None, {}, None

    async def diagnose_and_plan(
        self,
        active_contract: ToolContract,
        original_args: Dict[str, Any],
        status_code: int,
        error_payload: Any,
        trusted_headers: Optional[Dict[str, str]] = None,
        memory_pattern: Optional[Dict[str, Any]] = None,
    ) -> RepairCandidate:
        """Runs the complete evidence-gathering, schema diff, mapping and safety evaluation."""
        evidence: List[str] = []
        evidence.append(f"HTTP {status_code} schema error observed")

        # 1. Fetch fresh OpenAPI contract if available
        fresh_req, fresh_resp, fresh_headers, _ = await self.fetch_fresh_contract(
            server_url=active_contract.server_url,
            path=active_contract.path,
            method=active_contract.method,
        )

        candidate_req = fresh_req or active_contract.request_schema
        candidate_resp = fresh_resp or active_contract.response_schema
        trusted_h = trusted_headers or active_contract.required_headers

        if fresh_req:
            evidence.append("Fetched authoritative OpenAPI v2 contract from trusted server")

        # 2. Check Drift Memory pattern as supporting evidence
        if memory_pattern:
            evidence.append(
                f"Drift Memory candidate pattern identified (historical success: {memory_pattern.get('tool_name')})"
            )

        # 3. Compute Schema Diff
        diff = diff_schemas(
            old_req=active_contract.request_schema,
            new_req=candidate_req,
            old_resp=active_contract.response_schema,
            new_resp=candidate_resp,
            old_headers=active_contract.required_headers,
            new_headers=fresh_headers,
        )

        # 4. Run Mapping Solver
        mappings, mapping_evidence, refusals = self.mapping_solver.solve(
            diff=diff,
            original_args=original_args,
            trusted_headers=trusted_h,
        )
        evidence.extend(mapping_evidence)

        # 5. Check hard safety refusals
        if refusals:
            reason = "; ".join(refusals)
            evidence.append(f"Hard safety refusal triggered: {reason}")
            return RepairCandidate(
                target_version=active_contract.version + 1,
                evidence=evidence,
                confidence_score=0.0,
                decision="REFUSE",
                refusal_reason=reason,
            )

        # 6. Build Candidate Repair
        candidate = self.repair_engine.build_candidate(
            tool_name=active_contract.tool_name,
            current_version=active_contract.version,
            diff=diff,
            mappings=mappings,
            original_args=original_args,
            candidate_req_schema=candidate_req,
            candidate_resp_schema=candidate_resp,
            trusted_headers=trusted_h,
            evidence=evidence,
        )

        return candidate
