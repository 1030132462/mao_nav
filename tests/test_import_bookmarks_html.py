import textwrap
import unittest

from import_bookmarks_html import (
    BookmarkImportService,
    CATEGORY_IDS,
    load_mock_data_js,
    normalize_site_name,
    normalize_url,
    should_skip_url,
)


class NormalizeUrlTestCase(unittest.TestCase):
    def test_normalize_url_removes_default_port_fragment_and_trackers(self):
        url = "HTTPS://Example.com:443/tools/?utm_source=test&utm_medium=email&id=1#section"
        self.assertEqual(normalize_url(url), "https://example.com/tools?id=1")

    def test_normalize_url_preserves_significant_query(self):
        url = "https://example.com/search?q=vue+3&lang=zh"
        self.assertEqual(normalize_url(url), "https://example.com/search?lang=zh&q=vue+3")

    def test_should_skip_special_links(self):
        for url in [
            "",
            "javascript:void(0)",
            "mailto:test@example.com",
            "tel:10086",
            "chrome://settings",
            "chrome-extension://foo/bar",
            "file:///tmp/demo.html",
            "about:blank",
        ]:
            with self.subTest(url=url):
                self.assertTrue(should_skip_url(url))

    def test_normalize_url_collapses_known_session_pages(self):
        self.assertEqual(
            normalize_url("https://chatgpt.com/c/69339a98-4044-832c-bfa9-d3c15def5fb9"),
            "https://chatgpt.com",
        )
        self.assertEqual(
            normalize_url("https://gemini.google.com/app/94c95f5a7dac03bf"),
            "https://gemini.google.com/app",
        )
        self.assertEqual(
            normalize_url("https://linux.do/login"),
            "https://linux.do",
        )


class NormalizeSiteNameTestCase(unittest.TestCase):
    def test_normalize_site_name_compacts_whitespace(self):
        self.assertEqual(normalize_site_name("   ChatGPT   官方   "), "ChatGPT 官方")

    def test_normalize_site_name_uses_domain_when_name_missing(self):
        self.assertEqual(
            normalize_site_name("", fallback_url="https://docs.github.com/en"),
            "docs.github.com",
        )


class BookmarkImportServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.service = BookmarkImportService()

    def test_import_html_filters_deduplicates_and_maps_categories(self):
        html = textwrap.dedent(
            """
            <!DOCTYPE NETSCAPE-Bookmark-file-1>
            <DL><p>
              <DT><H3>开发资料</H3>
              <DL><p>
                <DT><A HREF="https://github.com/OpenAI/openai-python?utm_source=test"> OpenAI Python SDK </A>
                <DT><A HREF="https://github.com/openai/openai-python">OpenAI Python SDK</A>
                <DT><A HREF="javascript:void(0)">忽略链接</A>
              </DL><p>
              <DT><H3>AI 工具</H3>
              <DL><p>
                <DT><A HREF="https://chat.openai.com/">ChatGPT</A>
              </DL><p>
              <DT><H3>银行投资</H3>
              <DL><p>
                <DT><A HREF="https://xueqiu.com/">雪球</A>
              </DL><p>
            </DL><p>
            """
        )

        data = self.service.import_html_content(html, title="专属导航工作台")
        categories = {item["id"]: item for item in data["categories"]}

        self.assertEqual(len(data["categories"]), len(CATEGORY_IDS))
        self.assertEqual(data["title"], "专属导航工作台")
        self.assertEqual(data["search"], "bing")

        dev_sites = categories["development"]["sites"]
        self.assertEqual(len(dev_sites), 1)
        self.assertEqual(dev_sites[0]["normalizedUrl"], "https://github.com/OpenAI/openai-python")
        self.assertEqual(dev_sites[0]["sourceFolder"], "开发资料")

        common_sites = categories["common"]["sites"]
        self.assertEqual(common_sites[0]["name"], "ChatGPT")
        self.assertTrue(common_sites[0]["pinned"])

        finance_sites = categories["finance"]["sites"]
        self.assertEqual(finance_sites[0]["name"], "雪球")

    def test_import_html_uses_pending_when_folder_and_url_do_not_match(self):
        html = textwrap.dedent(
            """
            <!DOCTYPE NETSCAPE-Bookmark-file-1>
            <DL><p>
              <DT><H3>临时收集</H3>
              <DL><p>
                <DT><A HREF="https://example.org/anything">未分类链接</A>
              </DL><p>
            </DL><p>
            """
        )

        data = self.service.import_html_content(html)
        pending_sites = next(
            item["sites"] for item in data["categories"] if item["id"] == "pending"
        )
        self.assertEqual(len(pending_sites), 1)
        self.assertEqual(pending_sites[0]["sourceFolder"], "临时收集")
        self.assertEqual(pending_sites[0]["name"], "未分类链接")

    def test_load_mock_data_js_parses_export_prefix(self):
        text = textwrap.dedent(
            """
            export const mockData = {
              "title": "猫猫导航🐱",
              "search": "bing",
              "categories": []
            }
            """
        ).strip()

        data = load_mock_data_js(text)

        self.assertEqual(data["title"], "猫猫导航🐱")
        self.assertEqual(data["search"], "bing")
        self.assertEqual(data["categories"], [])

    def test_build_merge_preview_merges_existing_and_html_sources(self):
        existing_text = textwrap.dedent(
            """
            export const mockData = {
              "title": "猫猫导航🐱",
              "search": "bing",
              "categories": [
                {
                  "id": "my-favorites",
                  "name": "我的常用",
                  "icon": "💥",
                  "order": 0,
                  "sites": [
                    {
                      "id": "github",
                      "name": "GitHub",
                      "url": "https://github.com/",
                      "description": "代码托管平台",
                      "icon": "/sitelogo/github.com.ico"
                    },
                    {
                      "id": "risk",
                      "name": "RiskTest",
                      "url": "https://risk.copolits.com/",
                      "description": "检测风控",
                      "icon": "https://favicon.example/risk.ico"
                    }
                  ]
                }
              ]
            }
            """
        ).strip()
        html = textwrap.dedent(
            """
            <!DOCTYPE NETSCAPE-Bookmark-file-1>
            <DL><p>
              <DT><H3>常用</H3>
              <DL><p>
                <DT><A HREF="https://github.com?utm_source=test">GitHub 官方</A>
                <DT><A HREF="https://chatgpt.com/c/abc123">ChatGPT</A>
              </DL><p>
            </DL><p>
            """
        )

        preview = self.service.build_merge_preview(
            existing_data=load_mock_data_js(existing_text),
            html_content=html,
        )

        summary = preview["summary"]
        merged = preview["merged"]
        categories = {item["id"]: item for item in merged["categories"]}
        common_sites = {item["name"]: item for item in categories["common"]["sites"]}
        pending_sites = categories["pending"]["sites"]

        self.assertEqual(summary["existingSiteCount"], 2)
        self.assertEqual(summary["htmlSiteCount"], 2)
        self.assertEqual(summary["filteredCount"], 1)
        self.assertEqual(summary["deduplicatedSiteCount"], 3)
        self.assertIn("GitHub", common_sites)
        self.assertIn("ChatGPT", common_sites)
        self.assertEqual(common_sites["GitHub"]["icon"], "/sitelogo/github.com.ico")
        self.assertEqual(common_sites["GitHub"]["sourceType"], "merged")
        self.assertEqual(common_sites["ChatGPT"]["url"], "https://chatgpt.com")
        self.assertEqual(len(pending_sites), 1)
        self.assertEqual(pending_sites[0]["name"], "RiskTest")
        self.assertEqual(summary["categoryCounts"]["常用"], 2)
        self.assertEqual(summary["categoryCounts"]["待整理"], 1)
        self.assertTrue(summary["mergeExamples"])

    def test_build_merge_preview_keeps_design_tools_out_of_generic_tools(self):
        existing_text = textwrap.dedent(
            """
            export const mockData = {
              "title": "猫猫导航🐱",
              "search": "bing",
              "categories": [
                {
                  "id": "design",
                  "name": "设计工具",
                  "icon": "🎨",
                  "order": 0,
                  "sites": [
                    {
                      "id": "canva",
                      "name": "Canva",
                      "url": "https://www.canva.com/",
                      "description": "在线设计平台",
                      "icon": "/sitelogo/www.canva.com.ico"
                    }
                  ]
                }
              ]
            }
            """
        ).strip()

        preview = self.service.build_merge_preview(
            existing_data=load_mock_data_js(existing_text),
            html_content="<!DOCTYPE NETSCAPE-Bookmark-file-1><DL><p></DL><p>",
        )

        categories = {item["id"]: item for item in preview["merged"]["categories"]}
        self.assertEqual(len(categories["design"]["sites"]), 1)
        self.assertEqual(categories["design"]["sites"][0]["name"], "Canva")
        self.assertEqual(len(categories["tools"]["sites"]), 0)


if __name__ == "__main__":
    unittest.main()
