import pytest
from lxml import etree

from mdcx.config.enums import Language, Website
from mdcx.crawlers.base import get_crawler
from mdcx.crawlers.getchu import (
    GetchuCrawler,
    get_attestation_continue_url,
    get_extrafanart,
    get_title,
    normalize_detail_url,
)
from mdcx.crawlers.getchu_dl import scrape_dl_getchu
from mdcx.crawlers.getchu_dmm import GetchuDmmCrawler
from mdcx.models.types import CrawlerInput


class FakeGetchuClient:
    async def get_text(self, url, **kwargs):
        if url == "http://www.getchu.com/php/search.phtml?genre=all&search_keyword=TITLE-001&gc=gc":
            return (
                """
                <html><body>
                  <a class="blueb" href="../soft.phtml?id=1355679">TITLE-001 Sample</a>
                </body></html>
                """,
                "",
            )
        if url == "https://www.getchu.com/item/1355679/?gc=gc":
            return _detail_html(), ""
        return None, f"unexpected url: {url}"


class FakeDlGetchuClient:
    async def get_text(self, url, **kwargs):
        if url == "https://dl.getchu.com/i/item4068095":
            return _dl_detail_html(), ""
        if url.startswith("https://dl.getchu.com/search/search_list.php?"):
            return (
                """
                <html><body><table><tr>
                  <td valign="top"><div>
                    <a href="https://dl.getchu.com/i/item4068095">SEARCH-TITLE Sample</a>
                  </div></td>
                </tr></table></body></html>
                """,
                "",
            )
        return None, f"unexpected url: {url}"


def _dl_detail_html() -> str:
    return """
    <html>
      <head>
        <meta property="og:title" content="DLID-4068095 Sample" />
        <meta property="og:image" content="https://img.example/4068095.jpg" />
      </head>
      <body>
        <table>
          <tr><td>サークル</td><td>ハメモレモ</td></tr>
          <tr><td>配信開始日</td><td>2026/01/30</td></tr>
          <tr><td>作者</td><td>漏萌ミミオ</td></tr>
          <tr><td>画像数&ページ数</td><td>44分</td></tr>
          <tr><td>趣向</td><td><a>同人</a></td></tr>
          <tr><td>作品内容</td><td>紹介文</td></tr>
        </table>
      </body>
    </html>
    """


def _detail_html() -> str:
    return """
    <html>
      <head>
        <meta property="og:image" content="/brandnew/1355679/c1355679package.jpg" />
      </head>
      <body>
        <h1 id="soft-title">TITLE-001 Sample</h1>
        <td>品番：</td><td>TITLE-001</td>
        <td>発売日：</td><td><a>2026/04/03</a></td>
        <td>監督：</td><td>監督A</td>
        <td>時間：</td><td>88分</td>
        <td>サブジャンル：</td><td><a>アニメ</a><a>[一覧]</a></td>
        <a class="glance">メーカーA</a>
        <div class="tablebody">紹介文</div>
        <li class="genretab current">アダルトアニメ</li>
        <div class="item-Samplecard"><a class="highslide" href="/brandnew/1355679/sample.jpg"></a></div>
      </body>
    </html>
    """


def test_normalize_detail_url_converts_legacy_soft_url():
    url = "http://www.getchu.com/soft.phtml?id=1355679&gc=gc"
    assert normalize_detail_url(url) == "https://www.getchu.com/item/1355679/?gc=gc"


def test_get_attestation_continue_url_reads_continue_link():
    html = etree.fromstring(
        """
        <html>
          <body>
            <h1>年齢認証ページ</h1>
            <table>
              <tr>
                <td><a href="https://www.getchu.com/item/1355679/?gc=gc">【すすむ】</a></td>
              </tr>
            </table>
          </body>
        </html>
        """,
        etree.HTMLParser(),
    )

    assert get_attestation_continue_url(html) == "https://www.getchu.com/item/1355679/?gc=gc"


def test_get_title_falls_back_to_og_title():
    html = etree.fromstring(
        """
        <html>
          <head>
            <meta property="og:title" content="OVA シスターブリーダー ＃4  | ばにぃうぉ〜か〜" />
          </head>
          <body></body>
        </html>
        """,
        etree.HTMLParser(),
    )

    assert get_title(html) == "OVA シスターブリーダー ＃4"


def test_get_extrafanart_supports_new_item_samplecard_structure():
    html = etree.fromstring(
        """
        <html>
          <body>
            <div class="item-Samplecard-container">
              <div class="item-Samplecard">
                <a class="highslide" href="/brandnew/1355679/c1355679sample1.jpg"></a>
              </div>
              <div class="item-Samplecard">
                <a class="highslide" href="/brandnew/1355679/c1355679sample2.jpg"></a>
              </div>
            </div>
          </body>
        </html>
        """,
        etree.HTMLParser(),
    )

    assert get_extrafanart(html) == [
        "https://www.getchu.com/brandnew/1355679/c1355679sample1.jpg",
        "https://www.getchu.com/brandnew/1355679/c1355679sample2.jpg",
    ]


async def _run_crawler(crawler_class):
    crawler = crawler_class(client=FakeGetchuClient())
    return await crawler.run(
        CrawlerInput(
            appoint_number="",
            appoint_url="",
            file_path=None,
            mosaic="",
            number="TITLE-001",
            short_number="TITLE-001",
            language=Language.JP,
            org_language=Language.JP,
        )
    )


@pytest.mark.asyncio
async def test_getchu_crawler_uses_new_framework():
    res = await _run_crawler(GetchuCrawler)

    assert res.debug_info.error is None
    assert res.data is not None
    assert res.data.source == "getchu"
    assert res.data.number == "TITLE-001"
    assert res.data.title == "TITLE-001 Sample"
    assert res.data.release == "2026-04-03"
    assert res.data.year == "2026"
    assert res.data.runtime == "88"
    assert res.data.directors == ["監督A"]
    assert res.data.tags == ["アニメ"]
    assert res.data.studio == "メーカーA"
    assert res.data.mosaic == "里番"
    assert res.data.thumb == "http://www.getchu.com/brandnew/1355679/c1355679package.jpg"


@pytest.mark.asyncio
async def test_getchu_dmm_crawler_wraps_getchu_data():
    res = await _run_crawler(GetchuDmmCrawler)

    assert res.debug_info.error is None
    assert res.data is not None
    assert res.data.source == "getchu_dmm"
    assert res.data.title == "TITLE-001 Sample"


@pytest.mark.asyncio
async def test_dl_getchu_direct_number_initializes_detail_urls():
    crawler = GetchuCrawler(client=FakeDlGetchuClient())
    res = await crawler.run(
        CrawlerInput(
            appoint_number="",
            appoint_url="",
            file_path=None,
            mosaic="",
            number="DLID-4068095",
            short_number="DLID-4068095",
            language=Language.JP,
            org_language=Language.JP,
        )
    )

    assert res.debug_info.error is None
    assert res.debug_info.detail_urls == ["https://dl.getchu.com/i/item4068095"]
    assert res.data is not None
    assert res.data.number == "DLID-4068095"
    assert res.data.title == "DLID-4068095 Sample"


@pytest.mark.asyncio
async def test_dl_getchu_title_search_initializes_search_urls():
    from mdcx.crawlers.base import Context

    ctx = Context(
        input=CrawlerInput(
            appoint_number="",
            appoint_url="",
            file_path=None,
            mosaic="",
            number="SEARCH-TITLE",
            short_number="SEARCH-TITLE",
            language=Language.JP,
            org_language=Language.JP,
        )
    )

    data = await scrape_dl_getchu(FakeDlGetchuClient(), "SEARCH-TITLE", ctx=ctx)

    assert ctx.debug_info.search_urls
    assert ctx.debug_info.detail_urls == ["https://dl.getchu.com/i/item4068095"]
    assert data.number == "DLID-4068095"


def test_getchu_crawlers_are_registered():
    assert get_crawler(Website.GETCHU) is GetchuCrawler
    assert get_crawler(Website.GETCHU_DMM) is GetchuDmmCrawler
