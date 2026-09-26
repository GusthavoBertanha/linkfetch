from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from linkfetch.models import ResolvedDownload

FOCUS_STYLE = """
html, body { background: #111827 !important; min-height: 100% !important; }
body * { visibility: hidden !important; }
.linkfetch-focus, .linkfetch-focus * {
  visibility: visible !important;
}
.linkfetch-focus {
  position: fixed !important;
  inset: 0 !important;
  z-index: 2147483647 !important;
  display: flex !important;
  flex-direction: column !important;
  align-items: center !important;
  justify-content: center !important;
  width: 100vw !important;
  min-height: 100vh !important;
  margin: 0 !important;
  padding: 28px !important;
  background: #111827 !important;
}
"""


class BrowserResolutionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class BrowserTarget:
    name: str
    engine: str
    channel: str | None = None
    executable: Path | None = None


def _executable_from_command(command: str) -> Path | None:
    quoted = re.match(r'^\s*"([^"]+\.exe)"', command, re.IGNORECASE)
    if quoted:
        return Path(quoted.group(1))
    plain = re.match(r"^\s*([^ ]+\.exe)", command, re.IGNORECASE)
    return Path(plain.group(1)) if plain else None


def classify_browser(executable: Path) -> BrowserTarget | None:
    name = executable.name.lower()
    if name == "msedge.exe":
        return BrowserTarget("Microsoft Edge", "chromium", channel="msedge")
    if name == "chrome.exe":
        return BrowserTarget("Google Chrome", "chromium", channel="chrome")
    if name in {"brave.exe", "vivaldi.exe", "opera.exe", "opera_gx.exe"}:
        return BrowserTarget(executable.stem, "chromium", executable=executable)
    if name == "firefox.exe":
        return BrowserTarget("Mozilla Firefox", "firefox", executable=executable)
    return None


def windows_default_browser() -> BrowserTarget | None:
    if os.name != "nt":
        return None
    executable = _windows_associated_executable("https")
    if executable:
        target = classify_browser(executable)
        if target:
            return target
    try:
        import winreg

        choice_path = (
            r"Software\Microsoft\Windows\Shell\Associations"
            r"\UrlAssociations\https\UserChoice"
        )
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, choice_path) as key:
            prog_id, _ = winreg.QueryValueEx(key, "ProgId")
        with winreg.OpenKey(
            winreg.HKEY_CLASSES_ROOT,
            rf"{prog_id}\shell\open\command",
        ) as key:
            command, _ = winreg.QueryValueEx(key, "")
    except OSError:
        return None
    executable = _executable_from_command(command)
    return classify_browser(executable) if executable else None


def _windows_associated_executable(protocol: str) -> Path | None:
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        assoc_query = ctypes.windll.shlwapi.AssocQueryStringW
        assoc_query.argtypes = [
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        ]
        length = wintypes.DWORD(0)
        assoc_query(0, 2, protocol, None, None, ctypes.byref(length))
        if length.value == 0:
            return None
        buffer = ctypes.create_unicode_buffer(length.value)
        result = assoc_query(0, 2, protocol, None, buffer, ctypes.byref(length))
        return Path(buffer.value) if result == 0 and buffer.value else None
    except (AttributeError, OSError, ValueError):
        return None


def browser_candidates(preference: str | None = None) -> list[BrowserTarget]:
    preference = (preference or os.environ.get("LINKFETCH_BROWSER") or "auto").lower()
    known = {
        "edge": BrowserTarget("Microsoft Edge", "chromium", channel="msedge"),
        "chrome": BrowserTarget("Google Chrome", "chromium", channel="chrome"),
    }
    if preference in known:
        return [known[preference]]
    default = windows_default_browser()
    if preference == "default":
        return [default] if default else []
    candidates = [default] if default else []
    candidates.extend((known["edge"], known["chrome"]))
    unique: list[BrowserTarget] = []
    for candidate in candidates:
        if candidate not in unique:
            unique.append(candidate)
    return unique


def profile_directory() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    root = Path(base) if base else Path.home() / ".linkfetch"
    return root / "LinkFetch" / "browser-profile"


def launch_context(
    playwright: object,
    profile: Path,
    preference: str | None = None,
    *,
    headless: bool = False,
) -> object:
    failures: list[str] = []
    for target in browser_candidates(preference):
        if target.engine == "firefox":
            failures.append(
                f"{target.name}: the installed Firefox build is incompatible with the "
                "Playwright Chromium controller used by this mode"
            )
            continue
        options: dict[str, object] = {
            "headless": headless,
            "accept_downloads": False,
            # Playwright disables Chromium's sandbox unless explicitly asked not to.
            # Cloudflare treats the resulting --no-sandbox session as suspicious and
            # may reject a CAPTCHA that a person completed correctly.
            "chromium_sandbox": True,
            "viewport": {"width": 560, "height": 680},
            "args": ["--disable-notifications", "--disable-popup-blocking=false"],
        }
        if target.channel:
            options["channel"] = target.channel
        if target.executable:
            options["executable_path"] = str(target.executable)
        try:
            return playwright.chromium.launch_persistent_context(str(profile), **options)
        except Exception as exc:
            failures.append(f"{target.name}: {exc}")
    detail = "; ".join(failures) or "no compatible browser was detected"
    raise BrowserResolutionError(f"Could not open a controllable browser: {detail}")


def valid_resolved_url(page_url: str, candidate: str | None) -> str | None:
    if not candidate or candidate.strip() in {"", "#"}:
        return None
    resolved = urljoin(page_url, candidate)
    parsed = urlsplit(resolved)
    page = urlsplit(page_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    if parsed.hostname == page.hostname and parsed.path == page.path:
        return None
    return resolved


def resolve_focused_download(
    url: str,
    *,
    button_selector: str,
    focus_selector: str,
    timeout_seconds: int = 600,
) -> ResolvedDownload:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise BrowserResolutionError(
            "This link requires browser mode. Install it with: "
            "python -m pip install -e .[browser]"
        ) from exc

    profile = profile_directory()
    profile.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds

    with sync_playwright() as playwright:
        context = launch_context(playwright, profile)
        page = context.pages[0] if context.pages else context.new_page()

        def close_extra(opened: object) -> None:
            if opened is page:
                return
            try:
                opened.close()  # type: ignore[attr-defined]
            except Exception:
                pass

        context.on("page", close_extra)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            focus = page.locator(focus_selector).first
            focus.wait_for(state="attached", timeout=30_000)
            focus.evaluate("element => element.classList.add('linkfetch-focus')")
            page.add_style_tag(content=FOCUS_STYLE)
            page.bring_to_front()

            button = page.locator(button_selector).first
            while time.monotonic() < deadline:
                try:
                    href = button.get_attribute("href", timeout=1_000)
                    destination = valid_resolved_url(page.url, href)
                    disabled = button.get_attribute("aria-disabled", timeout=1_000)
                    if destination and disabled != "true":
                        cookies = context.cookies([destination])
                        cookie_header = "; ".join(
                            f"{cookie['name']}={cookie['value']}" for cookie in cookies
                        )
                        headers = {"Referer": page.url}
                        if cookie_header:
                            headers["Cookie"] = cookie_header
                        return ResolvedDownload(url=destination, headers=headers)
                except PlaywrightTimeoutError:
                    pass
                page.wait_for_timeout(250)
        except PlaywrightTimeoutError as exc:
            raise BrowserResolutionError(
                "The verification area did not appear or the completion window expired."
            ) from exc
        finally:
            context.close()

    raise BrowserResolutionError("Verification was not completed before the timeout.")


def acquire_cloudflare_session(url: str, *, timeout_seconds: int = 600) -> dict[str, str]:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise BrowserResolutionError(
            "This link requires browser mode. Install it with: "
            "python -m pip install -e .[browser]"
        ) from exc

    profile = profile_directory()
    profile.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds

    with sync_playwright() as playwright:
        context = launch_context(playwright, profile)
        page = context.pages[0] if context.pages else context.new_page()

        def close_extra(opened: object) -> None:
            if opened is page:
                return
            try:
                opened.close()  # type: ignore[attr-defined]
            except Exception:
                pass

        context.on("page", close_extra)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            page.bring_to_front()
            while time.monotonic() < deadline:
                try:
                    title = page.title().lower()
                    body = page.locator("body").inner_text(timeout=2_000).lower()
                except PlaywrightTimeoutError:
                    page.wait_for_timeout(500)
                    continue
                challenge = (
                    "just a moment" in title
                    or "security verification" in body
                )
                if not challenge:
                    cookies = context.cookies([page.url])
                    cookie_header = "; ".join(
                        f"{cookie['name']}={cookie['value']}" for cookie in cookies
                    )
                    user_agent = page.evaluate("() => navigator.userAgent")
                    headers = {"Referer": page.url, "User-Agent": user_agent}
                    if cookie_header:
                        headers["Cookie"] = cookie_header
                    return headers
                page.wait_for_timeout(500)
        except PlaywrightTimeoutError as exc:
            raise BrowserResolutionError(
                "Cloudflare verification did not load or was not completed."
            ) from exc
        finally:
            context.close()

    raise BrowserResolutionError("Cloudflare verification was not completed before the timeout.")
