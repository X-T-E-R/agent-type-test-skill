from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from website_adapters import get_adapter_profile, list_adapter_profiles


def _probe_site(args: argparse.Namespace) -> int:
    profile = get_adapter_profile(args.adapter)
    output_path = Path(args.output).resolve() if args.output else None
    request_urls: list[str] = []
    script_urls: list[str] = []

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not args.show_browser)
            context = browser.new_context()
            page = context.new_page()

            def on_request(request: Any) -> None:
                url = request.url
                if url not in request_urls:
                    request_urls.append(url)
                if request.resource_type == "script" and url not in script_urls:
                    script_urls.append(url)

            page.on("request", on_request)
            try:
                page.goto(profile.discovery_url, wait_until="domcontentloaded", timeout=args.timeout_ms)
            except PlaywrightTimeoutError:
                pass
            page.wait_for_timeout(args.settle_ms)
            title = page.title()
            final_url = page.url
            html = page.content()
            buttons = page.locator("button, a").all_inner_texts()[: args.max_controls]
            matched_dom_markers = [marker for marker in profile.dom_markers if marker.lower() in html.lower()]
            matched_network_markers = [
                marker
                for marker in profile.network_markers
                if any(marker.lower() in request_url.lower() for request_url in request_urls)
            ]
            matched_result_markers = [marker for marker in profile.result_markers if marker.lower() in html.lower()]
            payload = {
                "adapter": profile.id,
                "label": profile.label,
                "family": profile.family,
                "requested_url": profile.discovery_url,
                "final_url": final_url,
                "title": title,
                "matched_dom_markers": matched_dom_markers,
                "matched_network_markers": matched_network_markers,
                "matched_result_markers": matched_result_markers,
                "control_texts": buttons,
                "request_urls": request_urls[: args.max_requests],
                "script_urls": script_urls[: args.max_requests],
            }
            browser.close()
    except PlaywrightError as exc:
        raise SystemExit(
            "Playwright probe failed. If Chromium is missing, run `python -m playwright install chromium` first. "
            f"Details: {exc}"
        )

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


def _list_profiles(_: argparse.Namespace) -> int:
    print(json.dumps(list_adapter_profiles(), ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Playwright-backed browser adapter utilities.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_profiles = subparsers.add_parser("list", help="List built-in site adapter profiles")
    list_profiles.set_defaults(func=_list_profiles)

    probe = subparsers.add_parser("probe", help="Open an adapter URL and collect browser-side hints")
    probe.add_argument("--adapter", required=True, help="Built-in adapter id")
    probe.add_argument("--output", default=None, help="Optional output JSON path")
    probe.add_argument("--timeout-ms", type=int, default=20000)
    probe.add_argument("--settle-ms", type=int, default=3000)
    probe.add_argument("--max-requests", type=int, default=30)
    probe.add_argument("--max-controls", type=int, default=20)
    probe.add_argument("--show-browser", action="store_true")
    probe.set_defaults(func=_probe_site)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
