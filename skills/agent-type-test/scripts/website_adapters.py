from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class WebsiteAdapterProfile:
    id: str
    label: str
    family: str
    entry_url: str
    discovery_url: str
    capture_strategy: str
    status: str
    short_intro: str
    dom_markers: tuple[str, ...]
    network_markers: tuple[str, ...]
    result_markers: tuple[str, ...]
    notes: tuple[str, ...]


BUILTIN_WEBSITE_ADAPTERS: tuple[WebsiteAdapterProfile, ...] = (
    WebsiteAdapterProfile(
        id="16personalities",
        label="16Personalities",
        family="mbti",
        entry_url="https://www.16personalities.com/",
        discovery_url="https://www.16personalities.com/free-personality-test",
        capture_strategy="browser",
        status="implemented",
        short_intro="标准 MBTI 风格在线测试站，已接 staged browser flow，可分批发题并从结果页抽取类型和维度。",
        dom_markers=("Take the Test", "main-quiz", "question", "personality"),
        network_markers=("boot.", "build/assets", "google-analytics", "fonts.googleapis.com"),
        result_markers=("result", "personality type", "mind", "energy"),
        notes=(
            "Browser adapter now answers the native 10-step flow.",
            "Supports partial AI disclosure by auto-filling untouched questions with neutral answers.",
        ),
    ),
    WebsiteAdapterProfile(
        id="sbti-bilibili",
        label="SBTI Bilibili",
        family="sbti",
        entry_url="https://www.bilibili.com/blackboard/era/WijKT2bWuCJWPg8B.html",
        discovery_url="https://www.bilibili.com/blackboard/era/WijKT2bWuCJWPg8B.html",
        capture_strategy="browser",
        status="implemented",
        short_intro="B 站黑板活动页，已接 staged browser flow，可从整页题单里分批发题并抓结果页主类型与 15 维评分。",
        dom_markers=("SBTI", "result", "poster", "question"),
        network_markers=("activity.hdslb.com", "ReporterPb", "biliMirror", "log-reporter"),
        result_markers=("finalType", "poster", "intro", "desc"),
        notes=(
            "Browser adapter extracts the full question list after entering the test.",
            "Result parser reads the visible result panel, type label, match text, and 15 dimension cards.",
        ),
    ),
    WebsiteAdapterProfile(
        id="dtti",
        label="DTTI",
        family="dtti",
        entry_url="https://justmonikangel.github.io/-/",
        discovery_url="https://justmonikangel.github.io/-/",
        capture_strategy="browser",
        status="implemented",
        short_intro="GitHub Pages 上的前端人格测试，题库和计分逻辑都在页面脚本里，适合本地提取后 staged 执行。",
        dom_markers=("welcome", "test", "question", "result"),
        network_markers=("api.qrserver.com", "react", "react-dom", "tailwindcss"),
        result_markers=("CHARACTER_PROFILES", "result", "case_files"),
        notes=(
            "GitHub Pages app, likely front-end rendered.",
            "Implemented as a website-backed scripted extractor plus staged runner.",
        ),
    ),
)


def list_adapter_profiles() -> list[dict[str, Any]]:
    return [asdict(item) for item in BUILTIN_WEBSITE_ADAPTERS]


def match_adapter_by_url(url: str) -> dict[str, Any] | None:
    normalized = url.rstrip("/")
    for item in BUILTIN_WEBSITE_ADAPTERS:
        if normalized.startswith(item.entry_url.rstrip("/")):
            return asdict(item)
    return None


def get_adapter_profile(adapter_id: str) -> WebsiteAdapterProfile:
    for item in BUILTIN_WEBSITE_ADAPTERS:
        if item.id == adapter_id:
            return item
    raise KeyError(f"unknown adapter id: {adapter_id}")
