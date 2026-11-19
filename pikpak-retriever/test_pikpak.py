# -*- coding: utf-8 -*-
"""
PikPak 资源检索器 - 自动化测试
================================
用法（WorkBuddy 本地 / Muse 云端都一样，标准库 only，不用 pip）：
  python test_pikpak.py              # 只跑离线测试：解析器、去重、CSV、批量逻辑
  python test_pikpak.py --live 蜘蛛侠  # 离线 + 真网冒烟：跑一次真实搜索并写报告
  python test_pikpak.py --live       # 关键词默认 蜘蛛侠

跑完会在本目录生成 TEST_REPORT.md：时间、Python 版本、离线 PASS/FAIL、
真网各来源条数、DDG 无标题比例。离线失败 -> 退出码 1；真网失败只记在报告里，
不影响离线退出码（网络限流是对方定的，不是代码错）。
"""
import csv
import importlib.util
import os
import platform
import sys
import tempfile
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

def _load():
    spec = importlib.util.spec_from_file_location(
        "PikPakRetriever", os.path.join(HERE, "PikPakRetriever.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

PR = _load()

DDG_CLASSIC = '''
<div class="result results_links_deep">
<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fmypikpak.com%2Fs%2FABC123&rut=xxx">蜘蛛侠 4K</a>
<a class="result__snippet" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fmypikpak.com%2Fs%2FABC123">蜘蛛侠 4K 蓝光收藏</a>
</div>
<div class="result results_links_deep">
<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fmypikpak.com%2Fs%2FDEF456&rut=xxx">狂飙 全集</a>
<a class="result__snippet" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fmypikpak.com%2Fs%2FDEF456">狂飙 全集高清</a>
</div>
'''

DDG_HREF_FIRST = '''
<div class="result">
<a href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fmypikpak.com%2Fs%2FGHI789&rut=xxx" class="result__a">流浪地球2</a>
</div>
'''

DDG_DOUBLE_ENCODED = '''
<div class="result">
<a class="result__a" href="//duckduckgo.com/l/?uddg=https%253A%252F%252Fmypikpak.com%252Fs%252FXYZ999&rut=xxx">双重编码测试</a>
</div>
'''

DDG_EMPTY_TITLE = '''
<div class="result">
<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fmypikpak.com%2Fs%2FEMPTY01&rut=xxx"></a>
<a class="result__snippet" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fmypikpak.com%2Fs%2FEMPTY01">用摘要补标题的电影</a>
</div>
'''

DDG_URL_TITLE = '''
<div class="result">
<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fmypikpak.com%2Fs%2FURL01&rut=xxx">mypikpak.com</a>
<a class="result__snippet" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fmypikpak.com%2Fs%2FURL01">网址不能当标题的电影</a>
</div>
'''

BING_RSS = '''<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel>
<item><title>蜘蛛侠 4K Shared by xxx | PikPak</title><link>https://mypikpak.com/s/ABC123</link></item>
<item><title>狂飙 全集</title><link>https://mypikpak.com/s/DEF456</link></item>
<item><title>重复的蜘蛛侠</title><link>https://mypikpak.com/s/ABC123</link></item>
</channel></rss>'''


class TestParsers(unittest.TestCase):
    def test_version(self):
        self.assertEqual(PR.VERSION, "1.1.1")

    def test_local_proxy_detection_exists(self):
        # WorkBuddy 2026-11-19 小修：本地代理自动探测，修 DDG/Google 连不通。
        # 回归用例：探测函数和端口表必须在，找不到代理时要返回 None 而不是崩。
        self.assertTrue(hasattr(PR, "_detect_proxy"))
        self.assertIn(7890, PR.LOCAL_PROXY_PORTS)
        self.assertIn(10809, PR.LOCAL_PROXY_PORTS)
        # fetch_url 必须走探测到的 opener，而不是裸 urlopen
        import inspect
        self.assertIn("_OPENER", inspect.getsource(PR.fetch_url))

    def test_ddg_classic(self):
        items = PR.parse_ddg_html(DDG_CLASSIC)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["title"], "蜘蛛侠 4K")
        self.assertEqual(items[0]["link"], "https://mypikpak.com/s/ABC123")
        self.assertEqual(items[1]["title"], "狂飙 全集")

    def test_ddg_href_first(self):
        # v1.1.0 的 bug：只认 class 在 href 前面的锚点，href 在前就全成无标题
        items = PR.parse_ddg_html(DDG_HREF_FIRST)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "流浪地球2")
        self.assertEqual(items[0]["link"], "https://mypikpak.com/s/GHI789")

    def test_ddg_double_encoded(self):
        items = PR.parse_ddg_html(DDG_DOUBLE_ENCODED)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["link"], "https://mypikpak.com/s/XYZ999")
        self.assertEqual(items[0]["title"], "双重编码测试")

    def test_ddg_empty_title_fallback_snippet(self):
        items = PR.parse_ddg_html(DDG_EMPTY_TITLE)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "用摘要补标题的电影")

    def test_ddg_url_title_not_used(self):
        items = PR.parse_ddg_html(DDG_URL_TITLE)
        self.assertEqual(len(items), 1)
        self.assertNotIn("mypikpak", items[0]["title"].lower())
        self.assertEqual(items[0]["title"], "网址不能当标题的电影")

    def test_ddg_lite(self):
        items = PR.parse_ddg_lite(DDG_CLASSIC)
        self.assertTrue(len(items) >= 2)
        self.assertTrue(all(i["title"] != "（无标题）" for i in items))

    def test_bing_rss(self):
        items = PR.parse_bing_rss(BING_RSS)
        self.assertEqual(len(items), 2)  # 第 3 条是重复链接，去重后剩 2 条
        self.assertEqual(items[0]["title"], "蜘蛛侠 4K")  # 标题尾巴 Shared by…| PikPak 要去掉
        self.assertEqual(items[0]["link"], "https://mypikpak.com/s/ABC123")

    def test_dedup_and_category(self):
        items = PR.dedup([
            {"title": "a", "link": "https://mypikpak.com/s/1"},
            {"title": "a2", "link": "https://mypikpak.com/s/1"},
            {"title": "b", "link": "https://mypikpak.com/s/2"},
        ])
        self.assertEqual(len(items), 2)
        self.assertEqual(PR.guess_category("蜘蛛侠电影"), "电影")
        self.assertEqual(PR.guess_category("无关键词标题"), "未分类")

    def test_export_csv_columns(self):
        items = [
            {"title": "蜘蛛侠 4K", "category": "电影", "link": "https://mypikpak.com/s/ABC123"},
            {"title": "狂飙", "category": "电视剧", "link": "https://mypikpak.com/s/DEF456"},
        ]
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "out.csv")
            n = PR.export_csv(path, items, "蜘蛛侠")
            self.assertEqual(n, 2)
            with open(path, encoding="utf-8-sig", newline="") as f:
                rows = list(csv.reader(f))
            self.assertEqual(rows[0], ["序号", "资源名称", "分类", "PikPak分享链接", "搜索关键词"])
            self.assertEqual(rows[1][1], "蜘蛛侠 4K")
            self.assertEqual(rows[1][4], "蜘蛛侠")
            self.assertEqual(rows[2][3], "https://mypikpak.com/s/DEF456")

    def test_parse_pasted_text(self):
        text = "蜘蛛侠 4K\nhttps://mypikpak.com/s/ABC123\n狂飙\nhttps://mypikpak.com/s/ABC123\n"
        items = PR.parse_pasted_text(text, "蜘蛛侠")
        self.assertEqual(len(items), 1)  # 同链接去重

    def test_search_batch_fake_sources(self):
        # 用假来源验证批量逻辑：按页取整，第一批抓满 100 条新结果就停，
        # 之后再翻两页没新结果就到底（search_batch 按页取整，会略超 100，
        # 所以这里用 60+40 正好 100 条来测）
        def fake_search(name, keyword, page=1):
            if page == 1:
                return ([{"title": "片%d" % i, "link": "https://mypikpak.com/s/F%d" % i}
                         for i in range(60)], "ok")
            if page == 2:
                return ([{"title": "片%d" % i, "link": "https://mypikpak.com/s/F%d" % i}
                         for i in range(60, 100)], "ok")
            return ([], "empty")
        with mock.patch.object(PR, "search_source", side_effect=fake_search):
            state = PR.new_batch_state()
            batch1, _ = PR.search_batch("测试", ["Fake"], state)
            self.assertEqual(len(batch1), 100)
            # 去重：同一批里再跑一次不应重复
            self.assertEqual(len({i["link"] for i in batch1}), 100)
            batch2, _ = PR.search_batch("测试", ["Fake"], state)
            self.assertEqual(len(batch2), 0)


def run_live(keyword):
    """真网冒烟：只在 --live 时跑，网络限流不算代码失败，记在报告里。"""
    out = {"keyword": keyword, "sources": {}, "total": 0, "ddg_no_title_ratio": None, "csv_ok": False}
    state = PR.new_batch_state()
    try:
        items, statuses = PR.search_batch(keyword, ["Bing RSS", "DuckDuckGo"], state)
        out["sources"] = statuses
        out["total"] = len(items)
        ddg = [i for i in items if i.get("source") == "DuckDuckGo"]
        if ddg:
            out["ddg_no_title_ratio"] = sum(1 for i in ddg if i["title"] == "（无标题）") / len(ddg)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "live.csv")
            out["csv_ok"] = PR.export_csv(path, items, keyword) == len(items)
    except Exception as e:  # noqa: BLE001 - 真网冒烟不崩，记下来就行
        out["error"] = repr(e)
    return out


def main(argv):
    live_keyword = None
    if "--live" in argv:
        i = argv.index("--live")
        live_keyword = argv[i + 1] if i + 1 < len(argv) and not argv[i + 1].startswith("-") else "蜘蛛侠"
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestParsers)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    live = run_live(live_keyword) if live_keyword else None
    report = [
        "# TEST_REPORT",
        "",
        "- 时间：%s" % time.strftime("%Y-%m-%d %H:%M:%S"),
        "- Python：%s / %s" % (platform.python_version(), platform.platform()),
        "- 版本：%s" % PR.VERSION,
        "- 离线测试：%d 通过，%d 失败，%d 出错" % (
            result.testsRun - len(result.failures) - len(result.errors),
            len(result.failures), len(result.errors)),
    ]
    for kind, lst in (("失败", result.failures), ("出错", result.errors)):
        for test, tb in lst:
            report.append("- %s：%s" % (kind, test))
            report.append("  ```")
            report.append(tb.strip().splitlines()[-1] if tb.strip() else "")
            report.append("  ```")
    if live is not None:
        report.append("- 真网冒烟（关键词 %s）：共 %d 条，CSV 导出 %s" % (
            live["keyword"], live["total"], "通过" if live.get("csv_ok") else "失败"))
        for name, st in live.get("sources", {}).items():
            report.append("  - %s：%s" % (name, st))
        if live.get("ddg_no_title_ratio") is not None:
            report.append("  - DDG 无标题比例：%.0f%%" % (live["ddg_no_title_ratio"] * 100))
        if live.get("error"):
            report.append("  - 真网出错：%s" % live["error"])
    else:
        report.append("- 真网冒烟：未跑（加 --live 才跑）")
    with open(os.path.join(HERE, "TEST_REPORT.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(report) + "\n")
    print("\n报告已写到 TEST_REPORT.md")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
