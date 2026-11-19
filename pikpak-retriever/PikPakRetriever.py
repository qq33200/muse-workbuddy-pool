# -*- coding: utf-8 -*-
"""
PikPak 资源检索器 - Windows 本地版
=====================================
只做技术聚合：提取、去重、排除已有、导出。不做任何内容筛选，
搜到什么就显示什么，资源由使用者自己判断。

为什么做成本地程序？
  网页版在浏览器里不能直接跨域抓搜索引擎，只能走免费公共代理中转，
  代理一限流（522/429/408）三个来源就全挂。
  本地程序直接用你自己的网络去请求搜索引擎，没有浏览器跨域限制，
  也不经过公共代理，所以稳得多。

来源（全部直接请求，不走任何中转代理）：
  Bing RSS  - 最稳，有结构化标题+链接，实测“蜘蛛侠”一次返回 10 条
  Bing 网页 - 备用，解析页面里的 PikPak 直链
  DuckDuckGo- 备用，解析 html 版结果页（被限流时会返回空，要等一会儿）
  Google    - 可选，经常 429 限流，通了就有结果，不通就显示失败，不影响其他来源

运行方法（Windows）：
  1. 安装 Python 3.10 以上（去 python.org 下载，安装时勾选 Add Python to PATH，
     官方安装包自带 tkinter，不用另外装任何库）。
  2. 双击 PikPakRetriever.py 打开窗口。
  3. 输入关键词 -> 点“聚合搜索” -> 勾选想要的 -> 点“导出已选为 CSV”。
  命令行用法（不用开窗口，直接出结果）：
     python PikPakRetriever.py --cli 蜘蛛侠
     python PikPakRetriever.py --cli 蜘蛛侠 --out 结果.csv

导出的 CSV 列和之前的一致：
  序号、资源名称、分类、PikPak分享链接、搜索关键词
"""

import csv
import html as html_lib
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from queue import Queue

VERSION = "1.1.1"
CSV_COLUMNS = ["序号", "资源名称", "分类", "PikPak分享链接", "搜索关键词"]
CATEGORIES = ["未分类", "电影", "电视剧", "动漫", "综艺", "纪录片", "音乐",
              "软件", "资料", "小说", "其他"]

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
LINK_RE = re.compile(r"https?://mypikpak\.com/s/[A-Za-z0-9_\-]+(?:/[A-Za-z0-9_\-]+)?")


# ---------------------------------------------------------------- 基础工具

def fetch_url(url, timeout=20, retries=1):
    """直接 GET 一个 URL，返回 (状态码, 文本)。失败返回 (0, '')。"""
    last_err = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            })
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                text = raw.decode("utf-8", "ignore")
                return resp.status, text
        except urllib.error.HTTPError as e:
            last_err = "HTTP %s" % e.code
            if e.code in (429, 403) and attempt < retries:
                time.sleep(2)
                continue
            try:
                return e.code, e.read().decode("utf-8", "ignore")
            except Exception:
                return e.code, ""
        except Exception as e:  # 超时、断网、DNS 等
            last_err = str(e)[:80]
            if attempt < retries:
                time.sleep(2)
    return 0, ""


def clean_title(title):
    """去掉 Bing 标题尾巴的 ' Shared by xxx | PikPak' 这类后缀。"""
    title = html_lib.unescape((title or "").strip())
    title = re.sub(r"\s+Shared by.*$", "", title, flags=re.I)
    title = re.sub(r"\s*[\|\-–—]\s*PikPak\s*$", "", title, flags=re.I)
    title = re.sub(r"\s+", " ", title).strip()
    return title or "（无标题）"


def clean_link(link):
    link = (link or "").strip().rstrip("/")
    return link


def guess_category(title):
    t = title or ""
    for key, cat in [("纪录片", "纪录片"), ("综艺", "综艺"), ("动漫", "动漫"),
                     ("动画", "动漫"), ("电视剧", "电视剧"), ("连续剧", "电视剧"),
                     ("音乐", "音乐"), ("演唱会", "音乐"), ("软件", "软件"),
                     ("小说", "小说"), ("电影", "电影")]:
        if key in t:
            return cat
    return "未分类"


def dedup(items):
    seen, out = set(), []
    for it in items:
        key = it["link"]
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


# ---------------------------------------------------------------- 各来源解析

def parse_bing_rss(text):
    """Bing RSS：<item><title>…</title><link>https://mypikpak.com/s/…</link>"""
    items = []
    if not text or "<item>" not in text:
        return items
    try:
        root = ET.fromstring(text)
    except Exception:
        return items
    for node in root.iter("item"):
        title = node.findtext("title") or ""
        link = clean_link(node.findtext("link") or "")
        if link and "mypikpak.com/s/" in link:
            items.append({"title": clean_title(title), "link": link})
    return dedup(items)


def parse_bing_html(text):
    items = []
    for m in re.finditer(
            r'<a[^>]+href="(https?://mypikpak\.com/s/[^"]+)"[^>]*>(.*?)</a>',
            text or "", flags=re.I | re.S):
        link = clean_link(html_lib.unescape(m.group(1)))
        title = clean_title(re.sub(r"<[^>]+>", "", m.group(2)))
        if link and title != "（无标题）":
            items.append({"title": title, "link": link})
    if not items:  # 兜底：页面里出现直链但没包在 <a> 里
        for link in LINK_RE.findall(text or ""):
            items.append({"title": "（无标题）", "link": clean_link(link)})
    return dedup(items)


def _ddg_link_from_href(href):
    """从 DuckDuckGo 跳转链接里还原真实 PikPak 地址。
    形如 //duckduckgo.com/l/?uddg=<url 编码后的真地址>&rut=...。"""
    href = html_lib.unescape(href or "")
    m = re.search(r"uddg=([^&]+)", href)
    if m:
        try:
            target = urllib.parse.unquote(m.group(1))
            if "mypikpak.com/s/" not in target:
                target = urllib.parse.unquote(target)  # 有时是双重编码
        except Exception:
            return ""
        mm = LINK_RE.search(target)
        return clean_link(mm.group(0)) if mm else ""
    mm = LINK_RE.search(href)
    return clean_link(mm.group(0)) if mm else ""


def _looks_like_url(s):
    """锚点文字如果是网址/域名（如结果下方显示的 mypikpak.com），不能当标题。"""
    s = (s or "").strip().lower()
    if not s:
        return True
    if s.startswith("http") or s.startswith("www.") or "mypikpak" in s:
        return True
    return re.match(r"^[a-z0-9.-]+\.[a-z]{2,}(/|$)", s) is not None


def parse_ddg_html(text):
    """DuckDuckGo html 版：结果链接是 //duckduckgo.com/l/?uddg=<url 编码后的真地址>。
    标题和链接必须从同一个结果里一起取。页面结构会变（属性顺序、class 名都可能
    换），所以按 <div class="result ..."> 结果块切分，块内取标题链接的文字当标题；
    标题为空时用块内摘要补。v1.1.0 只认 class 在 href 前面的 result__a 锚点，
    真实页面稍有不同就全成（无标题），这版不再依赖这些细节。"""
    items = []
    text = text or ""
    blocks = re.split(r'<div class="result[\s"]', text)
    for block in blocks[1:]:
        link, title = "", ""
        for a in re.finditer(
                r'<a\b[^>]*href=(["\'])(.*?)\1[^>]*>(.*?)</a>',
                block, flags=re.I | re.S):
            l = _ddg_link_from_href(a.group(2))
            if not l:
                continue
            t = clean_title(re.sub(r"<[^>]+>", "", a.group(3)))
            if t == "（无标题）" or _looks_like_url(t):
                t = ""
            if not link:
                link, title = l, t
            elif t and not title:
                title = t
            if link and title:
                break
        if not link:
            continue
        if not title:
            sm = re.search(r'class="result__snippet"[^>]*>(.*?)</a>',
                           block, flags=re.S)
            if sm:
                title = clean_title(re.sub(r"<[^>]+>", "", sm.group(1)))
                if len(title) > 60:
                    title = title[:60] + "…"
        items.append({"title": title or "（无标题）", "link": link})
    if not items:
        # 兜底：块切分失败（页面换了外层结构）时，全页扫锚点
        for m in re.finditer(
                r'<a\b[^>]*href=(["\'])(.*?)\1[^>]*>(.*?)</a>',
                text, flags=re.I | re.S):
            link = _ddg_link_from_href(m.group(2))
            if not link:
                continue
            title = clean_title(re.sub(r"<[^>]+>", "", m.group(3)))
            if _looks_like_url(title):
                title = "（无标题）"
            items.append({"title": title, "link": link})
    return dedup(items)


def parse_ddg_lite(text):
    """DuckDuckGo lite 版备用解析：不依赖固定 class，任何指向 PikPak 的锚点都取。"""
    items = []
    for m in re.finditer(
            r'<a\b[^>]*href=(["\'])(.*?)\1[^>]*>(.*?)</a>',
            text or "", flags=re.I | re.S):
        link = _ddg_link_from_href(m.group(2))
        if not link:
            continue
        title = clean_title(re.sub(r"<[^>]+>", "", m.group(3)))
        if _looks_like_url(title):
            title = "（无标题）"
        items.append({"title": title, "link": link})
    return dedup(items)


def parse_google_html(text):
    items = []
    for m in re.finditer(r"/url\?q=(https?://mypikpak\.com/s/[^\"'&]+)", text or ""):
        link = clean_link(urllib.parse.unquote(m.group(1)))
        items.append({"title": "（无标题）", "link": link})
    for link in LINK_RE.findall(text or ""):
        items.append({"title": "（无标题）", "link": clean_link(link)})
    return dedup(items)


# ---------------------------------------------------------------- 搜索

def search_source(name, keyword, page=1):
    """搜一个来源。返回 (条目列表, 状态说明)。page 从 1 开始，每页约 20 条。"""
    q = urllib.parse.quote("site:mypikpak.com/s/ " + keyword)
    first = (page - 1) * 20 + 1
    if name == "Bing RSS":
        url = ("https://www.bing.com/search?format=rss&q=%s&count=20&first=%d"
               % (q, first))
        status, text = fetch_url(url)
        if status != 200:
            return [], "Bing RSS：请求失败（HTTP %s），稍后重试" % status
        items = parse_bing_rss(text)
        return items, ("Bing RSS：%d 条" % len(items)) if items else "Bing RSS：无结果"
    if name == "Bing 网页":
        url = ("https://www.bing.com/search?q=%s&count=20&first=%d"
               % (q, first))
        status, text = fetch_url(url)
        if status != 200:
            return [], "Bing 网页：请求失败（HTTP %s），稍后重试" % status
        items = parse_bing_html(text)
        return items, ("Bing 网页：%d 条" % len(items)) if items else "Bing 网页：无结果（Bing 结果常需脚本加载，RSS 已覆盖 Bing）"
    if name == "DuckDuckGo":
        # html 版每页约 30 条，用 s 做翻页偏移；202 常是机器人验证页，没有真结果
        url = ("https://html.duckduckgo.com/html/?q=%s&s=%d"
               % (q, (page - 1) * 30))
        status, text = fetch_url(url)
        if status not in (200, 202):
            return [], "DuckDuckGo：请求失败（HTTP %s），稍后重试" % status
        items = parse_ddg_html(text)
        if not items:
            # html 版没出结果时，试 lite 版（结构更简单，有时能绕开）
            status2, text2 = fetch_url(
                "https://lite.duckduckgo.com/lite/?q=" + q)
            if status2 in (200, 202):
                items = parse_ddg_lite(text2)
        if items:
            n_no_title = sum(1 for it in items
                             if it["title"] == "（无标题）")
            if n_no_title > len(items) // 2:
                # 一半以上没标题：把原始页面存下来，方便发给开发者排查结构
                try:
                    with open("ddg_debug.html", "w", encoding="utf-8") as f:
                        f.write(text)
                except Exception:
                    pass
                return items, ("DuckDuckGo：%d 条（%d 条无标题，已保存 ddg_debug.html）"
                               % (len(items), n_no_title))
            return items, "DuckDuckGo：%d 条" % len(items)
        return items, "DuckDuckGo：无结果（可能被限流，等一会儿再试）"
    if name == "Google":
        url = "https://www.google.com/search?q=%s&num=20" % q
        status, text = fetch_url(url)
        if status == 429:
            return [], "Google：被限流（429），等一会儿再试，不影响其他来源"
        if status != 200:
            return [], "Google：请求失败（HTTP %s），稍后重试" % status
        items = parse_google_html(text)
        return items, ("Google：%d 条" % len(items)) if items else "Google：无结果"
    return [], "未知来源"


SOURCES = ["Bing RSS", "Bing 网页", "DuckDuckGo", "Google"]


BATCH_SIZE = 100  # 每批新结果的目标条数：点一次“聚合搜索”或“继续加载”，抓满 100 条新结果为止
MAX_ROUNDS_PER_BATCH = 30  # 一批最多翻 30 轮，防止某个来源一直出重复结果时死循环


def new_batch_state():
    """一批一批往下翻的状态：已见过的链接、每个来源翻到第几页。
    注意“翻到底”的判断只在一批之内有效：Bing RSS 这类来源有时会间歇性
    返回空，下一批（下一次点“继续加载”）会重新试，不会永久拉黑。"""
    return {"seen": set(), "page": {}}


def search_batch(keyword, sources, state):
    """抓一批新结果：各来源轮流往下翻页，直到攒够 BATCH_SIZE 条新结果，
    或所有来源在本批内都翻到底（连续两页没有新结果）。返回 (新条目, {来源: 状态})。
    没有上限——只要还有新结果，点“继续加载”就能一直往下翻。"""
    new_items, statuses = [], {}
    exhausted, empty_streak = set(), {}
    rounds = 0
    while len(new_items) < BATCH_SIZE and rounds < MAX_ROUNDS_PER_BATCH:
        rounds += 1
        progressed = False
        for name in sources:
            if name in exhausted or len(new_items) >= BATCH_SIZE:
                continue
            page = state["page"].get(name, 1)
            items, st = search_source(name, keyword, page)
            state["page"][name] = page + 1
            statuses[name] = st
            fresh = [it for it in items if it["link"] not in state["seen"]]
            if fresh:
                empty_streak[name] = 0
                for it in fresh:
                    it["source"] = name
                    it["category"] = guess_category(it["title"])
                    it["selected"] = True
                    state["seen"].add(it["link"])
                new_items.extend(fresh)
                progressed = True
            else:
                empty_streak[name] = empty_streak.get(name, 0) + 1
                if empty_streak[name] >= 2:
                    exhausted.add(name)
            time.sleep(0.3)  # 来源之间停一下，别被当成刷请求
        if not progressed:
            break
    return new_items, statuses


def parse_pasted_text(text, keyword=""):
    """解析粘贴回来的搜索结果页文本：提取 PikPak 直链，前面一行文字当标题。"""
    items = []
    for m in LINK_RE.finditer(text or ""):
        link = clean_link(m.group(0))
        before = (text or "")[:m.start()].strip().splitlines()
        title = before[-1].strip() if before else ""
        title = clean_title(re.sub(r"<[^>]+>", "", title)) if title else "（无标题）"
        if len(title) > 60:
            title = "（无标题）"
        items.append({"title": title, "link": link, "source": "粘贴",
                      "category": guess_category(title), "selected": True})
    return dedup(items)


def read_links_from_csv(path):
    """从旧 CSV 里读出已有的 PikPak 链接（用于排除）。"""
    links = set()
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            for row in reader:
                for cell in row:
                    for m in LINK_RE.finditer(cell or ""):
                        links.add(clean_link(m.group(0)))
    except Exception:
        pass
    return links


def export_csv(path, items, keyword):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(CSV_COLUMNS)
        for i, it in enumerate(items, 1):
            w.writerow([i, it.get("title", ""), it.get("category", "未分类"),
                        it.get("link", ""), keyword])
    return len(items)


# ---------------------------------------------------------------- 命令行模式

def cli_main(argv):
    import argparse
    p = argparse.ArgumentParser(description="PikPak 资源检索器（本地版）")
    p.add_argument("--cli", metavar="关键词", required=True)
    p.add_argument("--out", metavar="CSV路径", default="")
    p.add_argument("--sources", default="Bing RSS,Bing 网页,DuckDuckGo")
    args = p.parse_args(argv)
    keyword = args.cli
    sources = [s for s in args.sources.split(",") if s in SOURCES]
    print("正在搜索：%s  来源：%s" % (keyword, "、".join(sources)))
    state = new_batch_state()
    items = []
    batch_no = 0
    while batch_no < 10:  # 命令行一次翻到底（最多 10 批，每批 100 条）
        batch_no += 1
        new_items, statuses = search_batch(keyword, sources, state)
        for name, st in statuses.items():
            print("  第 %d 批 %s" % (batch_no, st))
        items.extend(new_items)
        print("第 %d 批新增 %d 条，累计 %d 条" % (batch_no, len(new_items), len(items)))
        if not new_items:
            print("没有更多结果了")
            break
    print("共 %d 条（已去重）" % len(items))
    for i, it in enumerate(items, 1):
        print("%d. [%s] %s  %s" % (i, it["source"], it["title"], it["link"]))
    if args.out:
        n = export_csv(args.out, items, keyword)
        print("已导出 %d 条 -> %s" % (n, args.out))
    return 0


# ---------------------------------------------------------------- 图形窗口（Windows）

def gui_main():
    import tkinter as tk
    from tkinter import filedialog, messagebox, simpledialog, ttk

    state = {"items": [], "excluded": set(), "keyword": "",
             "batch": new_batch_state(), "last_added": 0,
             "searching": False}
    q = Queue()

    root = tk.Tk()
    root.title("PikPak 资源检索器（本地版） v%s" % VERSION)
    root.geometry("980x640")

    # ---- 顶部：关键词 + 来源 + 搜索
    top = ttk.Frame(root, padding=10)
    top.pack(fill="x")
    ttk.Label(top, text="关键词：").pack(side="left")
    kw_var = tk.StringVar()
    kw_entry = ttk.Entry(top, textvariable=kw_var, width=32)
    kw_entry.pack(side="left", padx=(0, 10))
    kw_entry.bind("<Return>", lambda e: do_search())
    src_vars = {}
    for name in SOURCES:
        v = tk.BooleanVar(value=(name != "Google"))
        src_vars[name] = v
        ttk.Checkbutton(top, text=name, variable=v).pack(side="left")
    ttk.Button(top, text="聚合搜索", command=lambda: do_search()).pack(side="left", padx=8)
    ttk.Button(top, text="继续加载", command=lambda: do_search(more=True)).pack(side="left")

    # ---- 状态行
    status_var = tk.StringVar(value="就绪：输入关键词，点“聚合搜索”。本地直连，不走任何代理。")
    ttk.Label(root, textvariable=status_var, wraplength=960,
              foreground="#555").pack(fill="x", padx=10)

    # ---- 结果表
    cols = ("sel", "source", "title", "category", "link")
    tree = ttk.Treeview(root, columns=cols, show="headings", selectmode="browse")
    tree.heading("sel", text="选")
    tree.heading("source", text="来源")
    tree.heading("title", text="资源名称")
    tree.heading("category", text="分类")
    tree.heading("link", text="PikPak分享链接")
    tree.column("sel", width=36, anchor="center")
    tree.column("source", width=90)
    tree.column("title", width=330)
    tree.column("category", width=70)
    tree.column("link", width=380)
    tree.pack(fill="both", expand=True, padx=10, pady=6)

    vsb = ttk.Scrollbar(tree, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)

    def refresh_tree():
        tree.delete(*tree.get_children())
        for i, it in enumerate(state["items"]):
            tree.insert("", "end", iid=str(i), values=(
                "☑" if it.get("selected") else "☐", it.get("source", ""),
                it.get("title", ""), it.get("category", "未分类"),
                it.get("link", "")))
        count_var.set("共 %d 条，已选 %d 条" % (
            len(state["items"]),
            sum(1 for it in state["items"] if it.get("selected"))))

    def add_items(new_items):
        before = len(state["items"])
        have = {it["link"] for it in state["items"]}
        n_dup = n_ex = 0
        for it in new_items:
            if it["link"] in state["excluded"]:
                n_ex += 1
                continue
            if it["link"] in have:
                n_dup += 1
                continue
            have.add(it["link"])
            state["items"].append(it)
        refresh_tree()
        return len(state["items"]) - before, n_dup, n_ex

    def poll_queue():
        try:
            while True:
                kind, payload = q.get_nowait()
                if kind == "status":
                    status_var.set(payload)
                elif kind == "items":
                    n, n_dup, n_ex = add_items(payload)
                    state["last_added"] = n
                    status_var.set(status_var.get() +
                                   "  新增 %d 条（重复 %d，已排除 %d）" % (n, n_dup, n_ex))
                elif kind == "done":
                    state["searching"] = False
                    status_var.set("%s；共 %d 条" % (payload, len(state["items"])))
                    if state.get("last_added", 1) == 0:
                        messagebox.showinfo("没有更多了", "已经翻到底了，没有更多结果了。")
        except Exception:
            pass
        root.after(200, poll_queue)

    def run_search(keyword, sources):
        # 每批抓满 100 条新结果；翻到底（本批 0 条新结果）时由 done 处理提示
        state["last_added"] = -1  # 搜索中先置 -1，避免旧值触发“没有更多了”
        items, statuses = search_batch(keyword, sources, state["batch"])
        for name in sources:
            q.put(("status", statuses.get(name, "")))
        q.put(("items", items))
        q.put(("done", "本批完成：%s" % (
            "；".join(statuses.get(n, "") for n in sources),)))

    def do_search(more=False):
        keyword = kw_var.get().strip()
        if not keyword:
            messagebox.showwarning("提示", "请先输入关键词")
            return
        if state["searching"]:
            return
        sources = [n for n, v in src_vars.items() if v.get()]
        if not sources:
            messagebox.showwarning("提示", "请至少勾选一个来源")
            return
        state["keyword"] = keyword
        if not more:
            state["items"] = []
            state["batch"] = new_batch_state()
            refresh_tree()
        state["searching"] = True
        status_var.set("正在搜索“%s”（每批 100 条新结果，翻到底会提示）…"
                       % keyword)
        threading.Thread(target=run_search, args=(keyword, sources),
                         daemon=True).start()

    def toggle_selected(event):
        iid = tree.identify_row(event.y)
        if iid is None:
            return
        if tree.identify_column(event.x) != "#1":
            return
        idx = int(iid)
        it = state["items"][idx]
        it["selected"] = not it.get("selected")
        refresh_tree()

    tree.bind("<Button-1>", toggle_selected)

    # ---- 编辑选中行
    edit = ttk.Frame(root, padding=(10, 0, 10, 0))
    edit.pack(fill="x")
    ttk.Label(edit, text="选中行：").pack(side="left")
    name_var = tk.StringVar()
    ttk.Entry(edit, textvariable=name_var, width=46).pack(side="left", padx=4)
    cat_var = tk.StringVar(value="未分类")
    ttk.Combobox(edit, textvariable=cat_var, values=CATEGORIES,
                 width=10, state="readonly").pack(side="left", padx=4)

    def on_select(event):
        sel = tree.selection()
        if not sel:
            return
        it = state["items"][int(sel[0])]
        name_var.set(it.get("title", ""))
        cat_var.set(it.get("category", "未分类"))

    tree.bind("<<TreeviewSelect>>", on_select)

    def save_edit():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("提示", "请先在表格里点选一行")
            return
        it = state["items"][int(sel[0])]
        it["title"] = name_var.get().strip() or it["title"]
        it["category"] = cat_var.get()
        refresh_tree()

    ttk.Button(edit, text="保存修改", command=save_edit).pack(side="left", padx=4)
    ttk.Button(edit, text="复制链接", command=lambda: copy_link()).pack(side="left")

    def copy_link():
        sel = tree.selection()
        if not sel:
            return
        root.clipboard_clear()
        root.clipboard_append(state["items"][int(sel[0])]["link"])
        status_var.set("已复制链接")

    # ---- 下方操作按钮
    count_var = tk.StringVar(value="共 0 条，已选 0 条")
    btns = ttk.Frame(root, padding=10)
    btns.pack(fill="x")
    ttk.Label(btns, textvariable=count_var).pack(side="left")

    def select_all(v):
        for it in state["items"]:
            it["selected"] = v
        refresh_tree()

    ttk.Button(btns, text="全选", command=lambda: select_all(True)).pack(side="left", padx=4)
    ttk.Button(btns, text="全不选", command=lambda: select_all(False)).pack(side="left")
    ttk.Button(btns, text="反选", command=lambda: invert()).pack(side="left", padx=4)

    def invert():
        for it in state["items"]:
            it["selected"] = not it.get("selected")
        refresh_tree()

    def import_exclude():
        path = filedialog.askopenfilename(title="选择旧 CSV",
                                          filetypes=[("CSV 文件", "*.csv")])
        if not path:
            return
        links = read_links_from_csv(path)
        state["excluded"] |= links
        before = len(state["items"])
        state["items"] = [it for it in state["items"] if it["link"] not in links]
        refresh_tree()
        status_var.set("已导入旧 CSV：%d 个已有链接，本次排除了 %d 条" %
                       (len(links), before - len(state["items"])))

    ttk.Button(btns, text="导入旧CSV排除", command=import_exclude).pack(side="left", padx=4)

    def paste_parse():
        win = tk.Toplevel(root)
        win.title("粘贴搜索结果页")
        win.geometry("640x420")
        ttk.Label(win, text="打开 Bing / Google / DuckDuckGo 的搜索页，复制全部内容粘贴到这里：",
                  padding=8).pack(anchor="w")
        txt = tk.Text(win)
        txt.pack(fill="both", expand=True, padx=8)

        def do_parse():
            items = parse_pasted_text(txt.get("1.0", "end"), state["keyword"])
            n, n_dup, n_ex = add_items(items)
            status_var.set("粘贴解析：新增 %d 条（重复 %d，已排除 %d）" % (n, n_dup, n_ex))
            win.destroy()

        ttk.Button(win, text="解析并加入表格", command=do_parse).pack(pady=8)

    ttk.Button(btns, text="粘贴解析", command=paste_parse).pack(side="left", padx=4)

    def manual_add():
        link = simpledialog.askstring("手动添加", "粘贴 PikPak 分享链接：", parent=root)
        if not link:
            return
        m = LINK_RE.search(link)
        if not m:
            messagebox.showwarning("提示", "没找到 mypikpak.com/s/ 链接")
            return
        title = simpledialog.askstring("手动添加", "资源名称：", parent=root) or "（无标题）"
        add_items([{"title": title, "link": clean_link(m.group(0)),
                    "source": "手动", "category": "未分类", "selected": True}])

    ttk.Button(btns, text="手动添加", command=manual_add).pack(side="left", padx=4)

    def export_selected():
        chosen = [it for it in state["items"] if it.get("selected")]
        if not chosen:
            messagebox.showwarning("提示", "没有勾选任何条目")
            return
        path = filedialog.asksaveasfilename(
            title="导出 CSV", defaultextension=".csv",
            initialfile="pikpak_%s.csv" % (state["keyword"] or "结果"),
            filetypes=[("CSV 文件", "*.csv")])
        if not path:
            return
        n = export_csv(path, chosen, state["keyword"])
        messagebox.showinfo("完成", "已导出 %d 条到：\n%s" % (n, path))

    ttk.Button(btns, text="导出已选为 CSV", command=export_selected).pack(side="left", padx=4)

    def open_pakseek():
        import webbrowser
        kw = kw_var.get().strip()
        webbrowser.open("https://pakseek.com/?q=" + urllib.parse.quote(kw) if kw
                        else "https://pakseek.com/")

    ttk.Button(btns, text="在 PakSeek 里搜", command=open_pakseek).pack(side="left", padx=4)

    ttk.Label(root, text="只做技术聚合：提取、去重、排除已有、导出，不做内容筛选。",
              foreground="#888").pack(fill="x", padx=10, pady=(0, 8))

    root.after(200, poll_queue)
    root.mainloop()


def main():
    # 打包成 EXE 后，控制台代码页可能是 cp1252 等非中文编码，
    # 直接 print 中文会崩；强制用 UTF-8 输出，显示不了的字用 ? 代替也不崩。
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    argv = sys.argv[1:]
    if argv and argv[0] == "--cli":
        return cli_main(argv)
    gui_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
