#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chrome 书签 HTML 离线导入脚本。

读取 Chrome 导出的 `bookmarks.html`，生成当前项目兼容的 `mock_data.js`。
只依赖 Python 标准库，便于在本地快速处理真实书签文件。
"""

import argparse
import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable, List, NamedTuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

DEFAULT_TITLE = "专属导航工作台"
DEFAULT_SEARCH = "bing"
DEFAULT_OUTPUT = Path("src/mock/mock_data.js")
EXPORT_PREFIX = "export const mockData = "
LOCAL_ICON_DIR = Path("public/sitelogo")

TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "ref",
    "ref_src",
    "spm",
}

SKIPPED_SCHEMES = (
    "javascript:",
    "mailto:",
    "tel:",
    "chrome:",
    "chrome-extension:",
    "edge:",
    "file:",
    "about:",
    "data:",
    "blob:",
)

CATEGORY_DEFINITIONS = [
    {
        "id": "common",
        "name": "常用",
        "icon": "⭐",
        "keywords": ("常用", "我的常用", "快速访问", "daily", "favorite"),
        "domains": ("chat.openai.com", "chatgpt.com", "claude.ai"),
    },
    {
        "id": "work",
        "name": "工作",
        "icon": "💼",
        "keywords": ("工作", "办公", "协作", "项目", "管理", "团队", "文档", "表格", "办公协作"),
        "domains": ("notion.so", "www.notion.so", "trello.com", "asana.com", "linear.app"),
    },
    {
        "id": "development",
        "name": "开发",
        "icon": "🛠️",
        "keywords": ("开发", "开发工具", "编程", "代码", "程序", "技术", "文档", "sdk", "api", "git", "dev", "前端", "后端"),
        "domains": (
            "github.com",
            "gitlab.com",
            "stackoverflow.com",
            "developer.mozilla.org",
            "docs.github.com",
            "npmjs.com",
        ),
    },
    {
        "id": "ai",
        "name": "AI",
        "icon": "🤖",
        "keywords": ("ai", "人工智能", "模型", "大模型", "llm", "prompt", "智能"),
        "domains": (
            "chat.openai.com",
            "chatgpt.com",
            "claude.ai",
            "poe.com",
            "perplexity.ai",
            "huggingface.co",
        ),
    },
    {
        "id": "cloud",
        "name": "云与服务器",
        "icon": "☁️",
        "keywords": ("云", "服务器", "主机", "cdn", "dns", "运维", "部署", "docker", "k8s"),
        "domains": (
            "dash.cloudflare.com",
            "cloudflare.com",
            "vercel.com",
            "aws.amazon.com",
            "console.aliyun.com",
            "cloud.tencent.com",
            "huaweicloud.com",
        ),
    },
    {
        "id": "tools",
        "name": "工具",
        "icon": "🔧",
        "keywords": ("工具", "效率", "转换", "实用", "utility"),
        "domains": (
            "www.bejson.com",
            "excalidraw.com",
            "regex101.com",
            "convertio.co",
            "speedtest.net",
        ),
    },
    {
        "id": "learning",
        "name": "学习",
        "icon": "📚",
        "keywords": ("学习", "学习资源", "教程", "课程", "笔记", "知识", "阅读", "培训"),
        "domains": ("developer.mozilla.org", "vuejs.org", "react.dev", "python.org", "freecodecamp.org"),
    },
    {
        "id": "community",
        "name": "资讯社区",
        "icon": "📰",
        "keywords": ("社区", "社区论坛", "论坛", "资讯", "新闻", "博客", "订阅", "社区交流", "讨论", "娱乐", "休闲", "影音"),
        "domains": ("linux.do", "v2ex.com", "www.v2ex.com", "news.ycombinator.com", "sspai.com", "www.producthunt.com"),
    },
    {
        "id": "design",
        "name": "设计素材",
        "icon": "🎨",
        "keywords": ("设计", "设计工具", "素材", "配色", "图标", "字体", "原型", "灵感", "ui", "ux"),
        "domains": ("figma.com", "www.figma.com", "dribbble.com", "www.iconfont.cn", "fontawesome.com", "behance.net"),
    },
    {
        "id": "finance",
        "name": "金融投资",
        "icon": "💹",
        "keywords": ("投资", "财经", "财经投资", "股票", "基金", "银行", "理财", "金融", "交易"),
        "domains": ("xueqiu.com", "www.tradingview.com", "eastmoney.com", "www.eastmoney.com", "finance.sina.com.cn"),
    },
    {
        "id": "pending",
        "name": "待整理",
        "icon": "🗂️",
        "keywords": ("待整理", "稍后", "收集", "暂存", "分类", "未整理", "later", "inbox"),
        "domains": (),
    },
]

CATEGORY_IDS = [item["id"] for item in CATEGORY_DEFINITIONS]
CATEGORY_TEMPLATES = [
    {
        "id": item["id"],
        "name": item["name"],
        "icon": item["icon"],
        "order": index,
        "sites": [],
    }
    for index, item in enumerate(CATEGORY_DEFINITIONS)
]
CATEGORY_LOOKUP = {item["id"]: item for item in CATEGORY_DEFINITIONS}
PINNED_DOMAINS = {"chat.openai.com", "chatgpt.com", "claude.ai", "github.com"}
CASE_INSENSITIVE_PATH_HOSTS = {"github.com", "gitlab.com"}
GENERIC_FOLDER_NAMES = {
    "bookmarks bar",
    "mobile bookmarks",
    "other bookmarks",
    "书签栏",
    "收藏栏",
    "移动书签",
    "其他书签",
}
HOST_ALIASES = {
    "chat.openai.com": "chatgpt.com",
    "cn.tradingview.com": "www.tradingview.com",
    "figma.com": "www.figma.com",
}
SITE_PROFILES = {
    "https://aistudio.google.com": {
        "name": "Google AI Studio",
        "description": "Google 模型调试与 API 体验入口",
        "category": "ai",
        "pinned": False,
    },
    "https://chatgpt.com": {
        "name": "ChatGPT",
        "description": "OpenAI 对话与内容生成助手",
        "category": "common",
        "pinned": True,
    },
    "https://claude.ai": {
        "name": "Claude",
        "description": "Anthropic 长文本推理与写作助手",
        "category": "common",
        "pinned": True,
    },
    "https://gemini.google.com/app": {
        "name": "Google Gemini",
        "description": "Google 多模态对话与生成工具",
        "category": "common",
        "pinned": True,
    },
    "https://github.com": {
        "name": "GitHub",
        "description": "代码托管、协作与版本管理平台",
        "category": "common",
        "pinned": True,
    },
    "https://linux.do": {
        "name": "Linux.do",
        "description": "技术讨论与工具分享社区",
        "category": "community",
        "pinned": False,
    },
    "https://www.figma.com": {
        "name": "Figma",
        "description": "原型设计与团队协作工具",
        "category": "design",
        "pinned": False,
    },
    "https://www.canva.cn": {
        "name": "Canva可画",
        "description": "在线设计、模板编辑与视觉素材平台",
        "category": "design",
        "pinned": False,
    },
    "https://www.canva.com": {
        "name": "Canva",
        "description": "在线设计、演示与视觉模板平台",
        "category": "design",
        "pinned": False,
    },
    "https://www.notion.so": {
        "name": "Notion",
        "description": "项目文档与协作工作台",
        "category": "work",
        "pinned": False,
    },
    "https://www.tradingview.com": {
        "name": "TradingView",
        "description": "图表分析与市场跟踪平台",
        "category": "finance",
        "pinned": False,
    },
}
REMOVE_CANDIDATE_HOSTS = {
    "fast.catsapi.com",
    "ip-geoaddress-generator.pages.dev",
    "mail.chatgpt.org.uk",
    "risk.copolits.com",
}
REMOVE_CANDIDATE_NAMES = {"freemail", "risktest", "虚拟地址", "猫猫绘图"}


def compact_text(value: str) -> str:
    """压缩多余空白，统一文本格式。"""

    return re.sub(r"\s+", " ", unescape(value or "")).strip()


def should_skip_url(url: str) -> bool:
    """过滤浏览器内部链接和无效链接。"""

    candidate = compact_text(url).lower()
    if not candidate:
        return True
    return candidate.startswith(SKIPPED_SCHEMES)


def filter_folder_parts(folder_path: Iterable[str]) -> List[str]:
    parts = []
    for item in folder_path:
        cleaned = compact_text(item)
        if not cleaned or cleaned.lower() in GENERIC_FOLDER_NAMES:
            continue
        parts.append(cleaned)
    return parts


def get_site_profile(normalized_url: str) -> dict:
    return SITE_PROFILES.get(normalized_url, {})


def find_local_icon(normalized_url: str) -> str:
    hostname = urlsplit(normalized_url).netloc.lower()
    if not hostname:
        return ""
    for suffix in (".ico", ".png", ".svg", ".webp"):
        candidate = LOCAL_ICON_DIR / "{}{}".format(hostname, suffix)
        if candidate.is_file():
            return "/sitelogo/{}{}".format(hostname, suffix)
    return ""


def prefer_icon(existing_icon: str, normalized_url: str) -> str:
    icon = compact_text(existing_icon)
    if icon:
        return icon
    local_icon = find_local_icon(normalized_url)
    if local_icon:
        return local_icon
    return build_favicon_url(normalized_url)


def load_mock_data_js(text: str) -> dict:
    payload = text.strip()
    if not payload.startswith(EXPORT_PREFIX):
        raise ValueError("mock_data.js 缺少 export const mockData = 前缀")
    payload = payload[len(EXPORT_PREFIX) :].strip()
    if payload.endswith(";"):
        payload = payload[:-1].rstrip()
    return json.loads(payload)


def normalize_url(url: str) -> str:
    """规范化 URL，便于稳定去重。"""

    candidate = compact_text(url)
    if not candidate:
        return ""
    if should_skip_url(candidate):
        return ""

    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", candidate):
        candidate = f"https://{candidate.lstrip('/')}"

    parsed = urlsplit(candidate)
    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower()
    if scheme not in {"http", "https"} or not hostname:
        return ""
    hostname = HOST_ALIASES.get(hostname, hostname)

    port = parsed.port
    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    netloc = hostname if port in (None, 0) or default_port else f"{hostname}:{port}"

    path = parsed.path or ""
    if path:
        path = re.sub(r"/{2,}", "/", path)
        if path != "/":
            path = path.rstrip("/")
        else:
            path = ""
    if hostname == "chatgpt.com" and path.startswith("/c/"):
        path = ""
    elif hostname == "gemini.google.com" and path.startswith("/app/"):
        path = "/app"
    elif hostname == "linux.do" and path == "/login":
        path = ""
    elif hostname == "router.tumuer.me" and path.startswith("/console/"):
        path = "/console"
    elif hostname == "new.xychatai.com" and path.startswith("/pastel/"):
        path = "/pastel"

    query_items = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        lowered = key.lower()
        if lowered.startswith(TRACKING_QUERY_PREFIXES) or lowered in TRACKING_QUERY_KEYS:
            continue
        query_items.append((key, value))
    query = urlencode(sorted(query_items), doseq=True)

    return urlunsplit((scheme, netloc, path, query, ""))


def normalize_site_name(name: str, fallback_url: str = "") -> str:
    """规范化站点名称，没有名称时回退为域名。"""

    candidate = compact_text(name)
    candidate = candidate.strip(" -|·•")
    if candidate:
        return candidate

    normalized_url = normalize_url(fallback_url)
    if not normalized_url:
        return "未命名站点"

    parsed = urlsplit(normalized_url)
    return parsed.netloc or "未命名站点"


def build_favicon_url(url: str) -> str:
    normalized_url = normalize_url(url)
    if not normalized_url:
        return "/favicon.ico"
    return f"https://www.google.com/s2/favicons?sz=64&domain_url={normalized_url}"


def slugify(value: str) -> str:
    cleaned = compact_text(value).lower()
    cleaned = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", cleaned)
    return cleaned.strip("-") or "site"


def build_site_id(name: str, normalized_url: str) -> str:
    parsed = urlsplit(normalized_url)
    seed = f"{parsed.netloc}-{parsed.path}-{name}"
    return f"site-{slugify(seed)}"


def build_dedupe_key(normalized_url: str) -> str:
    parsed = urlsplit(normalized_url)
    path = parsed.path.lower() if parsed.netloc in CASE_INSENSITIVE_PATH_HOSTS else parsed.path
    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, ""))


def generate_description(name: str, folder_path: Iterable[str], category_name: str) -> str:
    folder_label = " / ".join(filter_folder_parts(folder_path))
    if folder_label:
        return f"来自 Chrome 书签「{folder_label}」，归档到{category_name}"
    return f"{name}，已归档到{category_name}"


class BookmarkRecord(NamedTuple):
    name: str
    href: str
    folder_path: List[str]


class ChromeBookmarkHTMLParser(HTMLParser):
    """解析 Chrome 导出的书签 HTML。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.records: List[BookmarkRecord] = []
        self.folder_stack: List[str] = []
        self.dl_folder_flags: List[bool] = []
        self.pending_folder_name = ""
        self.current_folder_text: List[str] = []
        self.current_link_text: List[str] = []
        self.current_href = ""
        self.capture_folder = False
        self.capture_link = False

    def handle_starttag(self, tag, attrs):
        attr_map = dict(attrs)
        lowered = tag.lower()
        if lowered == "h3":
            self.capture_folder = True
            self.current_folder_text = []
        elif lowered == "a":
            self.capture_link = True
            self.current_link_text = []
            self.current_href = attr_map.get("href", "")
        elif lowered == "dl":
            has_folder = bool(self.pending_folder_name)
            self.dl_folder_flags.append(has_folder)
            if has_folder:
                self.folder_stack.append(self.pending_folder_name)
                self.pending_folder_name = ""

    def handle_endtag(self, tag):
        lowered = tag.lower()
        if lowered == "h3":
            self.capture_folder = False
            self.pending_folder_name = compact_text("".join(self.current_folder_text)) or "未命名文件夹"
        elif lowered == "a":
            self.capture_link = False
            name = compact_text("".join(self.current_link_text))
            self.records.append(
                BookmarkRecord(
                    name=name,
                    href=self.current_href,
                    folder_path=list(self.folder_stack),
                )
            )
        elif lowered == "dl":
            if self.dl_folder_flags:
                had_folder = self.dl_folder_flags.pop()
                if had_folder and self.folder_stack:
                    self.folder_stack.pop()

    def handle_data(self, data):
        if self.capture_folder:
            self.current_folder_text.append(data)
        elif self.capture_link:
            self.current_link_text.append(data)


class BookmarkImportService:
    """将书签 HTML 转为当前项目的导航数据。"""

    def __init__(self):
        self.category_templates = deepcopy(CATEGORY_TEMPLATES)

    def parse_html(self, html_content: str) -> List[BookmarkRecord]:
        parser = ChromeBookmarkHTMLParser()
        parser.feed(html_content)
        return parser.records

    def import_html_content(
        self,
        html_content: str,
        title: str = DEFAULT_TITLE,
        search: str = DEFAULT_SEARCH,
    ) -> dict:
        imported_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        records = self.parse_html(html_content)
        html_candidates, skipped = self.build_html_candidates(records, imported_at)
        merged_sites, duplicate_count, _ = self.merge_candidates(html_candidates)
        skipped += duplicate_count
        categories = self.group_sites_by_category(merged_sites)

        return {
            "title": title,
            "search": search,
            "importMeta": {
                "source": "chrome-bookmarks-html",
                "generatedAt": imported_at,
                "totalImported": sum(len(item["sites"]) for item in categories),
                "skippedLinks": skipped,
                "categoryCount": len(categories),
            },
            "categories": categories,
        }

    def build_merge_preview(
        self,
        existing_data: dict,
        html_content: str,
        title: str = "",
        search: str = "",
    ) -> dict:
        imported_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        records = self.parse_html(html_content)
        html_candidates, html_skipped = self.build_html_candidates(records, imported_at)
        existing_candidates, existing_skipped = self.build_existing_candidates(existing_data, imported_at)
        merged_sites, duplicate_count, merge_examples = self.merge_candidates(
            existing_candidates + html_candidates
        )
        merged_title = compact_text(title) or compact_text(existing_data.get("title", "")) or DEFAULT_TITLE
        merged_search = compact_text(search) or compact_text(existing_data.get("search", "")) or DEFAULT_SEARCH
        categories = self.group_sites_by_category(merged_sites)
        filtered_count = html_skipped + existing_skipped + duplicate_count
        merged_data = {
            "title": merged_title,
            "search": merged_search,
            "importMeta": {
                "source": "merged-preview",
                "generatedAt": imported_at,
                "totalImported": sum(len(item["sites"]) for item in categories),
                "skippedLinks": filtered_count,
                "categoryCount": len(categories),
            },
            "categories": categories,
        }
        summary = self.build_preview_summary(
            merged_sites=merged_sites,
            existing_candidates=existing_candidates,
            html_record_count=len(records),
            existing_raw_count=self.count_existing_sites(existing_data),
            filtered_count=filtered_count,
            merge_examples=merge_examples,
        )
        return {
            "merged": merged_data,
            "summary": summary,
        }

    def count_existing_sites(self, existing_data: dict) -> int:
        return sum(len(item.get("sites", [])) for item in existing_data.get("categories", []))

    def build_html_candidates(self, records: List[BookmarkRecord], imported_at: str):
        candidates = []
        skipped = 0

        for record in records:
            normalized_url = normalize_url(record.href)
            if not normalized_url:
                skipped += 1
                continue
            filtered_path = filter_folder_parts(record.folder_path)
            site_name = self.resolve_site_name(record.name, normalized_url)
            category_id = self.resolve_category_from_values(
                folder_parts=filtered_path,
                site_name=site_name,
                normalized_url=normalized_url,
                description="",
            )
            category_name = CATEGORY_LOOKUP[category_id]["name"]
            site = self.build_site_candidate(
                site_name=site_name,
                normalized_url=normalized_url,
                category_id=category_id,
                description=generate_description(site_name, filtered_path, category_name),
                icon="",
                pinned=self.should_pin_from_parts(filtered_path, normalized_url, category_id),
                tags=self.build_tags_from_parts(filtered_path, category_name),
                source_folder=filtered_path[-1] if filtered_path else "",
                source_path=" / ".join(filtered_path),
                imported_at=imported_at,
                source_type="chrome-bookmarks-html",
                source_label="Chrome 书签",
            )
            candidates.append(site)

        return candidates, skipped

    def build_existing_candidates(self, existing_data: dict, imported_at: str):
        candidates = []
        skipped = 0

        for category in existing_data.get("categories", []):
            category_name = compact_text(category.get("name", ""))
            filtered_path = filter_folder_parts([category_name])
            for site in category.get("sites", []):
                normalized_url = normalize_url(site.get("url", ""))
                if not normalized_url:
                    skipped += 1
                    continue
                site_name = self.resolve_site_name(site.get("name", ""), normalized_url)
                category_id = self.resolve_category_from_values(
                    folder_parts=filtered_path,
                    site_name=site_name,
                    normalized_url=normalized_url,
                    description=site.get("description", ""),
                )
                if (
                    category_id == "common"
                    and not get_site_profile(normalized_url)
                    and urlsplit(normalized_url).netloc.lower() not in PINNED_DOMAINS
                ):
                    category_id = self.resolve_category_from_values(
                        folder_parts=[],
                        site_name=site_name,
                        normalized_url=normalized_url,
                        description=site.get("description", ""),
                    )
                site_candidate = self.build_site_candidate(
                    site_name=site_name,
                    normalized_url=normalized_url,
                    category_id=category_id,
                    description=self.resolve_description(
                        description=site.get("description", ""),
                        folder_parts=filtered_path,
                        category_id=category_id,
                        normalized_url=normalized_url,
                        source_type="project-existing",
                    ),
                    icon=site.get("icon", ""),
                    pinned=self.should_pin_from_parts(filtered_path, normalized_url, category_id),
                    tags=self.merge_unique_strings(self.build_tags_from_parts(filtered_path, CATEGORY_LOOKUP[category_id]["name"]), site.get("tags", [])),
                    source_folder=category_name,
                    source_path=category_name,
                    imported_at=imported_at,
                    source_type="project-existing",
                    source_label="原项目数据",
                )
                candidates.append(site_candidate)

        return candidates, skipped

    def resolve_category(self, record: BookmarkRecord, normalized_url: str) -> str:
        return self.resolve_category_from_values(
            folder_parts=record.folder_path,
            site_name=record.name,
            normalized_url=normalized_url,
            description="",
        )

    def resolve_category_from_values(
        self,
        folder_parts: Iterable[str],
        site_name: str,
        normalized_url: str,
        description: str,
        allow_common_hint: bool = True,
    ) -> str:
        profile = get_site_profile(normalized_url)
        if profile.get("category"):
            return profile["category"]

        filtered_parts = filter_folder_parts(folder_parts)
        folder_text = " ".join(filtered_parts).lower()
        site_text = "{} {} {}".format(site_name, normalized_url, description).lower()
        hostname = urlsplit(normalized_url).netloc.lower()
        common_hint = any(
            keyword.lower() in folder_text
            for keyword in CATEGORY_LOOKUP["common"]["keywords"]
        )

        matched_category = self.match_category_by_keywords(
            folder_text,
            exclude_ids={"common", "pending"},
        )
        if matched_category:
            return matched_category

        for item in CATEGORY_DEFINITIONS:
            if hostname in item["domains"]:
                return item["id"]

        matched_category = self.match_category_by_keywords(
            site_text,
            exclude_ids={"common", "pending"},
        )
        if matched_category:
            return matched_category

        if allow_common_hint and common_hint:
            return "common"

        return "pending"

    def match_category_by_keywords(self, text: str, exclude_ids=None) -> str:
        best_match = ("", 0, len(CATEGORY_DEFINITIONS))
        excluded = set(exclude_ids or set())

        for index, item in enumerate(CATEGORY_DEFINITIONS):
            if item["id"] in excluded:
                continue
            for keyword in item["keywords"]:
                lowered = keyword.lower()
                if lowered and lowered in text:
                    candidate = (item["id"], len(lowered), -index)
                    if candidate[1] > best_match[1] or (
                        candidate[1] == best_match[1] and candidate[2] > best_match[2]
                    ):
                        best_match = candidate

        return best_match[0]

    def should_pin(self, record: BookmarkRecord, normalized_url: str, category_id: str) -> bool:
        return self.should_pin_from_parts(record.folder_path, normalized_url, category_id)

    def should_pin_from_parts(self, folder_parts: Iterable[str], normalized_url: str, category_id: str) -> bool:
        hostname = urlsplit(normalized_url).netloc.lower()
        folder_text = " ".join(filter_folder_parts(folder_parts)).lower()
        profile = get_site_profile(normalized_url)
        return (
            profile.get("pinned", False)
            or
            category_id == "common"
            or hostname in PINNED_DOMAINS
            or "常用" in folder_text
            or "收藏栏" in folder_text
        )

    def build_tags(self, record: BookmarkRecord, category_name: str) -> List[str]:
        return self.build_tags_from_parts(record.folder_path, category_name)

    def build_tags_from_parts(self, folder_parts: Iterable[str], category_name: str) -> List[str]:
        tags = [category_name]
        for part in filter_folder_parts(folder_parts)[-2:]:
            cleaned = compact_text(part)
            if cleaned and cleaned not in tags:
                tags.append(cleaned)
        return tags

    def resolve_site_name(self, name: str, normalized_url: str) -> str:
        profile = get_site_profile(normalized_url)
        if profile.get("name"):
            return profile["name"]
        return normalize_site_name(name, fallback_url=normalized_url)

    def resolve_description(
        self,
        description: str,
        folder_parts: Iterable[str],
        category_id: str,
        normalized_url: str,
        source_type: str,
        site_name: str = "",
    ) -> str:
        cleaned = compact_text(description)
        if cleaned:
            return cleaned
        profile = get_site_profile(normalized_url)
        if profile.get("description"):
            return profile["description"]
        if source_type == "chrome-bookmarks-html":
            return generate_description(
                site_name or self.resolve_site_name("", normalized_url),
                folder_parts,
                CATEGORY_LOOKUP[category_id]["name"],
            )
        return ""

    def build_site_candidate(
        self,
        site_name: str,
        normalized_url: str,
        category_id: str,
        description: str,
        icon: str,
        pinned: bool,
        tags: Iterable[str],
        source_folder: str,
        source_path: str,
        imported_at: str,
        source_type: str,
        source_label: str,
    ) -> dict:
        merged_tags = self.merge_unique_strings(tags)
        return {
            "id": build_site_id(site_name, normalized_url),
            "name": site_name,
            "url": normalized_url,
            "description": description,
            "icon": prefer_icon(icon, normalized_url),
            "pinned": pinned,
            "tags": merged_tags,
            "sourceFolder": source_folder,
            "sourcePath": source_path,
            "normalizedUrl": normalized_url,
            "importedAt": imported_at,
            "sourceType": source_type,
            "categoryId": category_id,
            "_sourceLabels": [source_label],
            "_sourceKinds": [source_type],
        }

    def merge_unique_strings(self, *groups: Iterable[str]) -> List[str]:
        seen = []
        for group in groups:
            for item in group or []:
                cleaned = compact_text(item)
                if cleaned and cleaned not in seen:
                    seen.append(cleaned)
        return seen

    def merge_candidates(self, candidates: List[dict]):
        merged = {}
        duplicates = 0
        examples = []

        for candidate in candidates:
            key = build_dedupe_key(candidate["normalizedUrl"])
            current = merged.get(key)
            if current is None:
                merged[key] = candidate
                continue

            duplicates += 1
            merged_candidate = self.merge_two_sites(current, candidate)
            merged[key] = merged_candidate
            if len(examples) < 10:
                examples.append(
                    {
                        "normalizedUrl": merged_candidate["normalizedUrl"],
                        "keptName": merged_candidate["name"],
                        "sources": self.merge_unique_strings(
                            current.get("_sourceLabels", []),
                            candidate.get("_sourceLabels", []),
                        ),
                    }
                )

        return list(merged.values()), duplicates, examples

    def merge_two_sites(self, left: dict, right: dict) -> dict:
        winner, other = self.pick_preferred_site(left, right)
        merged_sources = self.merge_unique_strings(
            left.get("_sourceLabels", []),
            right.get("_sourceLabels", []),
        )
        merged_kinds = self.merge_unique_strings(
            left.get("_sourceKinds", []),
            right.get("_sourceKinds", []),
        )
        merged_tags = self.merge_unique_strings(left.get("tags", []), right.get("tags", []))
        category_id = winner.get("categoryId") or other.get("categoryId") or "pending"
        category_name = CATEGORY_LOOKUP[category_id]["name"]
        return {
            "id": build_site_id(winner["name"], winner["normalizedUrl"]),
            "name": self.resolve_site_name(winner["name"], winner["normalizedUrl"]),
            "url": winner["url"],
            "description": self.pick_best_description(left, right, category_name),
            "icon": self.pick_best_icon(left, right),
            "pinned": left.get("pinned", False) or right.get("pinned", False),
            "tags": merged_tags,
            "sourceFolder": winner.get("sourceFolder") or other.get("sourceFolder", ""),
            "sourcePath": " | ".join(
                self.merge_unique_strings(
                    [left.get("sourcePath", "")],
                    [right.get("sourcePath", "")],
                )
            ),
            "normalizedUrl": winner["normalizedUrl"],
            "importedAt": winner["importedAt"],
            "sourceType": "merged" if len(merged_kinds) > 1 else winner["sourceType"],
            "categoryId": category_id,
            "_sourceLabels": merged_sources,
            "_sourceKinds": merged_kinds,
        }

    def pick_preferred_site(self, left: dict, right: dict):
        left_score = self.score_site(left)
        right_score = self.score_site(right)
        if right_score > left_score:
            return right, left
        return left, right

    def score_site(self, site: dict) -> int:
        score = 0
        icon = compact_text(site.get("icon", ""))
        description = compact_text(site.get("description", ""))
        if site.get("sourceType") == "project-existing":
            score += 2
        if icon.startswith("/"):
            score += 3
        elif icon and "google.com/s2/favicons" not in icon:
            score += 2
        if description and "来自 Chrome 书签" not in description:
            score += 2
        elif description:
            score += 1
        if site.get("pinned"):
            score += 1
        if get_site_profile(site.get("normalizedUrl", "")):
            score += 1
        return score

    def pick_best_description(self, left: dict, right: dict, category_name: str) -> str:
        descriptions = [
            compact_text(left.get("description", "")),
            compact_text(right.get("description", "")),
        ]
        descriptions = [item for item in descriptions if item]
        for item in descriptions:
            if "来自 Chrome 书签" not in item:
                return item
        if descriptions:
            return descriptions[0]
        return generate_description(left["name"], [], category_name)

    def pick_best_icon(self, left: dict, right: dict) -> str:
        for candidate in (left.get("icon", ""), right.get("icon", "")):
            cleaned = compact_text(candidate)
            if cleaned.startswith("/"):
                return cleaned
        for candidate in (left.get("icon", ""), right.get("icon", "")):
            cleaned = compact_text(candidate)
            if cleaned and "google.com/s2/favicons" not in cleaned:
                return cleaned
        return prefer_icon(left.get("icon", "") or right.get("icon", ""), left["normalizedUrl"])

    def group_sites_by_category(self, sites: List[dict]) -> List[dict]:
        categories = deepcopy(self.category_templates)
        categories_by_id = {item["id"]: item for item in categories}

        for site in sites:
            category_id = site.get("categoryId", "pending")
            category = categories_by_id[category_id]
            exported = dict(site)
            exported.pop("categoryId", None)
            exported.pop("_sourceLabels", None)
            exported.pop("_sourceKinds", None)
            category["sites"].append(exported)

        for category in categories:
            category["sites"].sort(key=lambda item: (not item.get("pinned", False), item["name"].lower()))
        return categories

    def split_source_parts(self, source_path: str) -> List[str]:
        parts = []
        for group in compact_text(source_path).split("|"):
            for item in group.split("/"):
                cleaned = compact_text(item)
                if cleaned:
                    parts.append(cleaned)
        return parts

    def reassign_non_common_site(self, site: dict) -> str:
        category_id = self.resolve_category_from_values(
            folder_parts=self.split_source_parts(site.get("sourcePath", "")),
            site_name=site.get("name", ""),
            normalized_url=site.get("normalizedUrl", ""),
            description=site.get("description", ""),
            allow_common_hint=False,
        )
        if category_id == "common":
            return "pending"
        return category_id

    def rebuild_tags(self, site: dict, category_id: str) -> List[str]:
        filtered_tags = [
            compact_text(tag)
            for tag in site.get("tags", [])
            if compact_text(tag) and compact_text(tag) not in [item["name"] for item in CATEGORY_DEFINITIONS]
        ]
        return self.merge_unique_strings([CATEGORY_LOOKUP[category_id]["name"]], filtered_tags)

    def apply_manual_curation(
        self,
        merged_sites: List[dict],
        excluded_names=None,
        forced_common_names=None,
        forced_pending_names=None,
        forced_category_by_name=None,
    ):
        excluded = {compact_text(item) for item in (excluded_names or [])}
        forced_common = {compact_text(item) for item in (forced_common_names or [])}
        forced_pending = {compact_text(item) for item in (forced_pending_names or [])}
        forced_categories = {
            compact_text(name): category_id
            for name, category_id in (forced_category_by_name or {}).items()
        }

        curated_sites = []
        excluded_sites = []

        for original in merged_sites:
            site = dict(original)
            name_key = compact_text(site.get("name", ""))
            if name_key in excluded:
                excluded_sites.append(site)
                continue

            if name_key in forced_categories:
                category_id = forced_categories[name_key]
            elif name_key in forced_pending:
                category_id = "pending"
            elif site.get("categoryId") == "common" and name_key not in forced_common:
                category_id = self.reassign_non_common_site(site)
            else:
                category_id = site.get("categoryId", "pending")

            if name_key in forced_common:
                category_id = "common"

            site["categoryId"] = category_id
            site["pinned"] = name_key in forced_common
            site["tags"] = self.rebuild_tags(site, category_id)
            curated_sites.append(site)

        return curated_sites, excluded_sites

    def build_preview_summary(
        self,
        merged_sites: List[dict],
        existing_candidates: List[dict],
        html_record_count: int,
        existing_raw_count: int,
        filtered_count: int,
        merge_examples: List[dict],
    ) -> dict:
        category_counts = {}
        for category in CATEGORY_DEFINITIONS:
            category_counts[category["name"]] = len(
                [item for item in merged_sites if item.get("categoryId") == category["id"]]
            )

        common_sites = [
            item["name"]
            for item in merged_sites
            if item.get("categoryId") == "common"
        ]
        suggested_keep = [
            item["name"]
            for item in merged_sites
            if "原项目数据" in item.get("_sourceLabels", [])
            and (
                item.get("pinned")
                or compact_text(item.get("icon", "")).startswith("/")
                or get_site_profile(item.get("normalizedUrl", ""))
            )
        ]
        suggested_remove = [
            item["name"]
            for item in existing_candidates
            if self.is_remove_candidate(item)
        ]
        uncertain_sites = [
            item["name"]
            for item in merged_sites
            if item.get("categoryId") == "pending"
        ]
        return {
            "existingSiteCount": existing_raw_count,
            "htmlSiteCount": html_record_count,
            "filteredCount": filtered_count,
            "deduplicatedSiteCount": len(merged_sites),
            "categoryCounts": category_counts,
            "commonSites": common_sites,
            "suggestedKeepExisting": self.merge_unique_strings(suggested_keep)[:20],
            "suggestedRemoveExisting": self.merge_unique_strings(suggested_remove)[:20],
            "uncertainSites": self.merge_unique_strings(uncertain_sites)[:20],
            "mergeExamples": merge_examples,
        }

    def is_remove_candidate(self, site: dict) -> bool:
        hostname = urlsplit(site.get("normalizedUrl", "")).netloc.lower()
        name = compact_text(site.get("name", "")).lower()
        return (
            site.get("categoryId") == "pending"
            or hostname in REMOVE_CANDIDATE_HOSTS
            or name in REMOVE_CANDIDATE_NAMES
            or compact_text(site.get("sourceFolder", "")) == "DDDD"
        )


def render_mock_data_js(data: dict) -> str:
    return f"export const mockData = {json.dumps(data, ensure_ascii=False, indent=2)}\n"


def write_output_file(data: dict, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_mock_data_js(data), encoding="utf-8")
    return output_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="将 Chrome 导出的书签 HTML 转成 mock_data.js")
    parser.add_argument("input", help="Chrome 导出的书签 HTML 文件路径")
    parser.add_argument(
        "-o",
        "--output",
        default=str(DEFAULT_OUTPUT),
        help=f"输出文件路径，默认写入 {DEFAULT_OUTPUT}",
    )
    parser.add_argument("--title", default=DEFAULT_TITLE, help="生成后的导航标题")
    parser.add_argument("--search", default=DEFAULT_SEARCH, help="默认搜索引擎")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只解析并输出统计，不写入文件",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.is_file():
        parser.error(f"输入文件不存在: {input_path}")

    html_content = input_path.read_text(encoding="utf-8")
    service = BookmarkImportService()
    data = service.import_html_content(html_content, title=args.title, search=args.search)

    total_sites = sum(len(item["sites"]) for item in data["categories"])
    print(f"解析完成: {total_sites} 个站点，{len(data['categories'])} 个分类")

    if args.dry_run:
        print("dry-run 模式，未写入文件")
        return 0

    output_path = write_output_file(data, Path(args.output))
    print(f"已写入: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
