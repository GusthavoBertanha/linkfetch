from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from linkfetch.browser import BrowserResolutionError, launch_context, profile_directory
from linkfetch.models import ResolvedDownload
from linkfetch.resolvers.base import Resolver

ONEFICHIER_HOSTS = {"1fichier.com", "www.1fichier.com"}


class OneFichierResolutionError(ValueError):
    pass


class _FinalLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_anchor = False
        self.current_href: str | None = None
        self.current_classes = ""
        self.current_text: list[str] = []
        self.candidates: list[tuple[int, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        values = {key.lower(): value or "" for key, value in attrs}
        self.in_anchor = True
        self.current_href = values.get("href")
        self.current_classes = values.get("class", "").lower()
        self.current_text = []

    def handle_data(self, data: str) -> None:
        if self.in_anchor:
            self.current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self.in_anchor:
            return
        text = " ".join("".join(self.current_text).lower().split())
        score = 0
        if "download" in text:
            score += 50
        if "btn-orange" in self.current_classes or "ok" in self.current_classes.split():
            score += 30
        if self.current_href and score:
            self.candidates.append((score, self.current_href))
        self.in_anchor = False


def is_onefichier_link(url: str) -> bool:
    parsed = urlsplit(url)
    return (
        parsed.scheme in {"http", "https"}
        and (parsed.hostname or "").lower() in ONEFICHIER_HOSTS
        and bool(parsed.query)
    )


def extract_onefichier_result(html: str, page_url: str) -> str:
    lowered = html.lower()
    if "all free guest slots are currently in use" in lowered:
        raise OneFichierResolutionError(
            "1fichier reports that all free download slots are occupied. "
            "Try again later or use an account configured by the user."
        )
    parser = _FinalLinkParser()
    parser.feed(html)
    for _score, href in sorted(parser.candidates, reverse=True):
        candidate = urljoin(page_url, href)
        parsed = urlsplit(candidate)
        host = (parsed.hostname or "").lower()
        if parsed.scheme in {"http", "https"} and (
            host == "1fichier.com" or host.endswith(".1fichier.com")
        ):
            if parsed.path not in {"/login.pl", "/register.pl", "/tarifs.html"}:
                return candidate
    raise OneFichierResolutionError(
        "1fichier did not provide a final link after the free-tier wait."
    )


class OneFichierResolver(Resolver):
    def supports(self, url: str) -> bool:
        return is_onefichier_link(url)

    def resolve(self, url: str) -> ResolvedDownload:
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise BrowserResolutionError(
                "1fichier requires the browser component. Install it with: "
                "python -m pip install -e .[browser]"
            ) from exc

        with sync_playwright() as playwright:
            context = launch_context(playwright, profile_directory(), headless=True)
            page = context.pages[0] if context.pages else context.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                button = page.locator("#dlw")
                button.wait_for(state="attached", timeout=30_000)
                page.wait_for_function(
                    "() => !document.querySelector('#dlw')?.disabled",
                    timeout=120_000,
                )
                with page.expect_navigation(wait_until="domcontentloaded", timeout=60_000):
                    button.click()
                destination = extract_onefichier_result(page.content(), page.url)
                cookies = context.cookies([destination])
                cookie_header = "; ".join(
                    f"{cookie['name']}={cookie['value']}" for cookie in cookies
                )
                headers = {"Referer": page.url}
                if cookie_header:
                    headers["Cookie"] = cookie_header
                return ResolvedDownload(url=destination, headers=headers)
            except PlaywrightTimeoutError as exc:
                raise OneFichierResolutionError(
                    "The 1fichier free-tier wait did not finish within two minutes."
                ) from exc
            finally:
                context.close()
