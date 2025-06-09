from typing import Dict
import time
import aiohttp

async def verify_website_individually(site_name: str, site_config: dict) -> dict:
    """Step-by-step verification for each website"""
    verification_report = {
        "site_name": site_name,
        "status": "unknown",
        "tests": {
            "connectivity": False,
            "response_time": None,
            "content_accessible": False,
            "search_form_found": False,
            "sample_data_extracted": False,
            "rate_limit_compliant": False,
        },
        "errors": [],
        "recommendations": [],
    }

    base_url = site_config.get("base_url")
    if not base_url:
        verification_report["errors"].append("Missing base_url")
        verification_report["status"] = "failed"
        return verification_report

    start = time.monotonic()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(base_url, timeout=10) as resp:
                verification_report["tests"]["connectivity"] = resp.status < 400
                verification_report["tests"]["response_time"] = time.monotonic() - start
                verification_report["tests"]["content_accessible"] = resp.content_type in {"text/html", "application/json"}
                if resp.status == 429:
                    verification_report["tests"]["rate_limit_compliant"] = False
                else:
                    verification_report["tests"]["rate_limit_compliant"] = True
    except Exception as exc:  # pragma: no cover - network dependent
        verification_report["errors"].append(str(exc))
        verification_report["status"] = "failed"
        return verification_report

    verification_report["status"] = "passed" if verification_report["tests"]["connectivity"] else "failed"
    return verification_report

