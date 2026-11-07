"""news_bot 단위 테스트 (네트워크 없이 실행). python -m unittest tests.test_news_bot"""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from news_bot import __main__ as bot
from news_bot import filters
from news_bot.config import Credentials, Query, Settings, load_settings
from news_bot.naver import parse_items
from news_bot.store import Store
from news_bot.telegram import KST, format_digest, split_message

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)


def item(title, desc="", link="https://n.news.naver.com/a/1", orig="https://www.hankyung.com/a/1", hours_ago=1):
    pub = (NOW - timedelta(hours=hours_ago)).strftime("%a, %d %b %Y %H:%M:%S +0000")
    return {"title": title, "description": desc, "link": link, "originallink": orig, "pubDate": pub}


class NaverParseTest(unittest.TestCase):
    def test_strips_tags_and_entities(self):
        [a] = parse_items({"items": [item("<b>삼성전자</b> HBM &quot;양산&quot;")]})
        self.assertEqual(a.title, '삼성전자 HBM "양산"')
        self.assertEqual(a.source, "hankyung.com")
        self.assertTrue(a.is_naver_news)

    def test_skips_bad_date(self):
        bad = item("x")
        bad["pubDate"] = "garbage"
        self.assertEqual(parse_items({"items": [bad]}), [])


class NaverRequestTest(unittest.TestCase):
    def _capture(self, use_hub):
        from news_bot import naver
        resp = mock.MagicMock()
        resp.__enter__.return_value.read.return_value = b'{"items": []}'
        with mock.patch.object(naver.urllib.request, "urlopen", return_value=resp) as m:
            naver.search_news("커피", "ID", "SECRET", display=2, use_hub=use_hub)
        return m.call_args.args[0]

    def test_developers_endpoint(self):
        req = self._capture(False)
        self.assertTrue(req.full_url.startswith("https://openapi.naver.com/v1/search/news.json?"))
        self.assertEqual(req.get_header("X-naver-client-id"), "ID")

    def test_api_hub_endpoint(self):
        req = self._capture(True)
        self.assertTrue(req.full_url.startswith("https://naverapihub.apigw.ntruss.com/search/v1/news?"))
        self.assertIn("format=json", req.full_url)
        self.assertEqual(req.get_header("X-ncp-apigw-api-key-id"), "ID")
        self.assertEqual(req.get_header("X-ncp-apigw-api-key"), "SECRET")

    def test_hub_sample_response(self):
        # NAVER API HUB 문서의 응답 예시 (+0900 시간대)
        payload = {"items": [{
            "title": "인천시, 송도 아파트서 '마을기업 연계축제' 개최",
            "originallink": "https://www.gukjenews.com/news/articleView.html?idxno=3606281",
            "link": "https://www.gukjenews.com/news/articleView.html?idxno=3606281",
            "description": "<b>커피</b>드립백, 나전칠기 키링",
            "pubDate": "Thu, 11 Jun 2026 18:30:00 +0900"}]}
        [a] = parse_items(payload)
        self.assertEqual(a.source, "gukjenews.com")
        self.assertEqual(a.description, "커피드립백, 나전칠기 키링")
        self.assertFalse(a.is_naver_news)
        self.assertEqual(a.published.utcoffset(), timedelta(hours=9))


class FilterTest(unittest.TestCase):
    def setUp(self):
        self.articles = parse_items({"items": [
            item("삼성전자 HBM4 양산", orig="https://a.com/1"),
            item("삼성전자 특징주 급등", "HBM 기대감", orig="https://a.com/2"),
            item("삼성전자 노조 협상", orig="https://a.com/3"),
            item("삼성전자 파운드리 수주", orig="https://a.com/4", hours_ago=48),
            item("삼성전자  HBM4 양산!", orig="https://b.com/9"),  # 제목 중복
            item("HBM 공급 확대", link="https://b.com/5", orig="https://b.com/5"),
        ]})

    def test_conditions(self):
        q = Query(name="t", query="삼성전자", include_any=["HBM", "파운드리"], exclude=["특징주"], max_age_hours=24)
        titles = [a.title for a in filters.apply(self.articles, q, now=NOW)]
        self.assertEqual(titles, ["삼성전자 HBM4 양산", "HBM 공급 확대"])

    def test_naver_only_and_include_all(self):
        q = Query(name="t", query="x", include_all=["삼성전자", "HBM"], naver_only=True, max_age_hours=0)
        titles = [a.title for a in filters.apply(self.articles, q, now=NOW)]
        self.assertEqual(titles, ["삼성전자 HBM4 양산", "삼성전자 특징주 급등"])


class StoreTest(unittest.TestCase):
    def test_dedupe_by_link_and_title(self):
        with tempfile.TemporaryDirectory() as d:
            s = Store(Path(d) / "x.db")
            a, b, c = parse_items({"items": [
                item("기사 A", orig="https://a.com/1"),
                item("기사 A", orig="https://other.com/1"),
                item("기사 C", orig="https://a.com/3"),
            ]})
            s.mark_sent(a, "q")
            self.assertTrue(s.is_sent(a))
            self.assertTrue(s.is_sent(b))
            self.assertFalse(s.is_sent(c))
            s.set_state("k", "1")
            self.assertEqual(s.get_state("k"), "1")


class TelegramFormatTest(unittest.TestCase):
    def test_escapes_html(self):
        [a] = parse_items({"items": [item("A&amp;B &lt;신제품&gt; <b>출시</b>", "설명")]})
        text = format_digest("조건 <1>", [a])
        self.assertIn("A&amp;B &lt;신제품&gt; 출시", text)
        self.assertIn("조건 &lt;1&gt;", text)
        self.assertIn('href="https://n.news.naver.com/a/1"', text)

    def test_split(self):
        blocks = ["x" * 1500] * 5
        chunks = split_message("\n\n".join(blocks))
        self.assertTrue(all(len(c) <= 4096 for c in chunks))
        self.assertEqual(sum(c.count("x") for c in chunks), 7500)


class RunOnceTest(unittest.TestCase):
    def test_sends_once_then_dedupes(self):
        payload = {"items": [item("삼성전자 HBM 신제품", orig=f"https://a.com/{i}", hours_ago=0) if i == 0 else
                             item(f"삼성전자 HBM 뉴스 {i}", orig=f"https://a.com/{i}", hours_ago=0) for i in range(4)]}
        settings = Settings(queries=[Query(name="HBM", query="HBM", max_per_run=3)])
        creds = Credentials("id", "secret", "token", "-100123")
        tg = mock.Mock()
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(bot, "search_news", return_value=parse_items(payload)):
            store = Store(Path(d) / "x.db")
            self.assertEqual(bot.run_once(settings, creds, store, tg, force=True), 3)
            self.assertEqual(bot.run_once(settings, creds, store, tg, force=True), 1)
            self.assertEqual(bot.run_once(settings, creds, store, tg, force=True), 0)
        self.assertEqual(tg.send.call_count, 2)
        self.assertEqual(tg.send.call_args_list[0].args[0], "-100123")

    def test_quiet_hours_wraps_midnight(self):
        s = Settings(queries=[], quiet_hours=(22, 7))
        at = lambda h: datetime(2026, 11, 7, h, 0, tzinfo=KST)
        self.assertTrue(bot.in_quiet_hours(s, at(23)))
        self.assertTrue(bot.in_quiet_hours(s, at(3)))
        self.assertFalse(bot.in_quiet_hours(s, at(9)))


class ConfigTest(unittest.TestCase):
    def test_bundled_queries_load(self):
        settings = load_settings()
        self.assertTrue(settings.queries)


if __name__ == "__main__":
    unittest.main()
