from __future__ import annotations

import json
import os
import re
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

from linkfetch.models import ResolvedDownload


class WebViewCaptureError(ValueError):
    pass


def extract_filecrypt_link_ids(scripts: list[str]) -> list[str]:
    """Extract real FileCrypt link IDs from element onclick handlers."""
    result: list[str] = []
    for script in scripts:
        match = re.search(r"\bopenLink\(\s*['\"]([A-Za-z0-9_-]+)['\"]", script)
        if match and match.group(1) not in result:
            result.append(match.group(1))
    return result


def capture_filecrypt_links(url: str, *, timeout_seconds: int = 600) -> tuple[list[str], dict[str, str]]:
    if os.name != "nt":
        raise WebViewCaptureError("FileCrypt browser capture is available on Windows only.")
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or (parsed.hostname or "").lower() not in {
        "filecrypt.cc", "www.filecrypt.cc"
    }:
        raise WebViewCaptureError("The URL must be a FileCrypt container.")
    try:
        import webview
        from webview.platforms import edgechromium
    except ImportError as exc:
        raise WebViewCaptureError(
            "FileCrypt requires WebView2 support. Install it with: python -m pip install -e .[browser]"
        ) from exc

    captured: dict[str, object] = {}
    finished = threading.Event()
    link_route_started = threading.Event()
    original_new_window = edgechromium.EdgeChrome.on_new_window_request
    original_download = edgechromium.EdgeChrome.on_download_starting
    original_navigation = edgechromium.EdgeChrome.on_navigation_start

    def finish(destination: str) -> None:
        if finished.is_set():
            return
        captured["destinations"] = [destination]
        finished.set()
        threading.Thread(target=window.destroy, daemon=True).start()

    def on_new_window(self: object, sender: object, args: object) -> None:
        destination = str(args.get_Uri())  # type: ignore[attr-defined]
        args.set_Handled(True)  # type: ignore[attr-defined]
        host = (urlsplit(destination).hostname or "").lower()
        if host in FILECRYPT_BROWSER_HOSTS:
            if urlsplit(destination).path.lower().startswith("/link/"):
                link_route_started.set()
            self.load_url(destination)  # type: ignore[attr-defined]
        elif link_route_started.is_set() and urlsplit(destination).scheme in {"http", "https"}:
            finish(destination)

    def on_download(self: object, sender: object, args: object) -> None:
        args.Cancel = True  # type: ignore[attr-defined]

    def on_navigation(self: object, sender: object, args: object) -> None:
        destination = str(args.get_Uri())  # type: ignore[attr-defined]
        parsed_destination = urlsplit(destination)
        host = (parsed_destination.hostname or "").lower()
        if parsed_destination.scheme in {"about", "data"} or host in FILECRYPT_BROWSER_HOSTS:
            return
        if link_route_started.is_set() and parsed_destination.scheme in {"http", "https"}:
            args.Cancel = True  # type: ignore[attr-defined]
            finish(destination)
            return
        args.Cancel = True  # type: ignore[attr-defined]

    FILECRYPT_BROWSER_HOSTS = {"filecrypt.cc", "www.filecrypt.cc", "filecrypt.to", "www.filecrypt.to"}
    edgechromium.EdgeChrome.on_new_window_request = on_new_window
    edgechromium.EdgeChrome.on_download_starting = on_download
    edgechromium.EdgeChrome.on_navigation_start = on_navigation
    window = webview.create_window(
        "LinkFetch — complete the FileCrypt verification",
        url,
        width=900,
        height=820,
        resizable=True,
        text_select=True,
    )

    def start_monitor() -> None:
        if captured.get("monitor_started"):
            return
        captured["monitor_started"] = True

        def monitor() -> None:
            deadline = time.monotonic() + timeout_seconds
            opened_link = False
            while not finished.is_set() and time.monotonic() < deadline:
                try:
                    current_url = str(window.evaluate_js("location.href"))
                    parsed_current = urlsplit(current_url)
                    current_host = (parsed_current.hostname or "").lower()
                    if (
                        link_route_started.is_set()
                        and parsed_current.scheme in {"http", "https"}
                        and current_host
                        and current_host not in FILECRYPT_BROWSER_HOSTS
                    ):
                        finish(current_url)
                        return
                    scripts = window.evaluate_js(
                        """
                        (() => {
                          const matches = [];
                          for (const element of document.querySelectorAll('body *')) {
                            const text = (element.innerText || element.value || '').trim().toLowerCase();
                            const visible = !!(element.offsetWidth || element.offsetHeight || element.getClientRects().length);
                            if (!visible || text !== 'download') continue;
                            let target = element;
                            for (let depth = 0; target && depth < 6; depth++, target = target.parentElement) {
                              const source = target.getAttribute('onclick') ||
                                (target.onclick ? target.onclick.toString() : '') || '';
                              if (source.includes('openLink')) {
                                matches.push(source);
                                break;
                              }
                            }
                          }
                          if (matches.length) {
                            document.documentElement.style.visibility = 'hidden';
                          }
                          return matches;
                        })()
                        """
                    )
                    if isinstance(scripts, list):
                        ids = extract_filecrypt_link_ids([str(item) for item in scripts])
                        if ids and not opened_link:
                            if len(ids) != 1:
                                captured["error"] = (
                                    f"This FileCrypt container has {len(ids)} links. "
                                    "Batch containers are not supported yet."
                                )
                                finished.set()
                                window.destroy()
                                return
                            opened_link = True
                            link_route_started.set()
                            captured["user_agent"] = window.evaluate_js("navigator.userAgent")
                            cookies: list[tuple[str, str]] = []
                            for jar in window.get_cookies() or []:
                                cookies.extend((name, morsel.value) for name, morsel in jar.items())
                            captured["cookies"] = cookies
                            target = json.dumps(f"https://filecrypt.cc/Link/{ids[0]}.html")
                            window.run_js(f"location.href = {target}")
                            time.sleep(1)
                            continue
                    if opened_link and current_host in FILECRYPT_BROWSER_HOSTS:
                        window.run_js(
                            """
                            (() => {
                              const candidates = Array.from(document.querySelectorAll('a, button, input'));
                              const button = candidates.find(element => {
                                const text = (element.innerText || element.value || '').trim().toLowerCase();
                                const visible = !!(element.offsetWidth || element.offsetHeight || element.getClientRects().length);
                                return visible && (text === 'download' || text.includes('continue to download'));
                              });
                              if (button && button.dataset.linkfetchClicked !== 'true') {
                                button.dataset.linkfetchClicked = 'true';
                                button.click();
                              }
                            })();
                            """
                        )
                except Exception:
                    pass
                time.sleep(0.05)
            if not finished.is_set():
                captured["error"] = "FileCrypt verification timed out."
                finished.set()
                try:
                    window.destroy()
                except Exception:
                    pass

        threading.Thread(target=monitor, daemon=True).start()

    window.events.loaded += start_monitor
    try:
        webview.settings["ALLOW_DOWNLOADS"] = False
        webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = False
        webview.start(
            gui="edgechromium",
            debug=False,
            private_mode=True,
            storage_path=str(Path(os.environ.get("LOCALAPPDATA", Path.home())) / "LinkFetch" / "webview2"),
        )
    finally:
        edgechromium.EdgeChrome.on_new_window_request = original_new_window
        edgechromium.EdgeChrome.on_download_starting = original_download
        edgechromium.EdgeChrome.on_navigation_start = original_navigation
    destinations = captured.get("destinations")
    if not isinstance(destinations, list) or not destinations:
        raise WebViewCaptureError(str(captured.get("error") or "The window closed before FileCrypt was unlocked."))
    cookie_values = captured.get("cookies")
    cookie_header = ""
    if isinstance(cookie_values, list):
        cookie_header = "; ".join(
            f"{name}={value}" for name, value in cookie_values
            if isinstance(name, str) and isinstance(value, str)
        )
    headers = {"Referer": url}
    if cookie_header:
        headers["Cookie"] = cookie_header
    user_agent = captured.get("user_agent")
    if isinstance(user_agent, str) and user_agent:
        headers["User-Agent"] = user_agent
    return [str(item) for item in destinations], headers


def capture_download_click(url: str, *, button_selector: str | None = None) -> ResolvedDownload:
    if os.name != "nt":
        raise WebViewCaptureError("WebView2 capture is available on Windows only.")
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise WebViewCaptureError("The URL must use HTTP or HTTPS.")
    try:
        import webview
        from webview.platforms import edgechromium
    except ImportError as exc:
        raise WebViewCaptureError(
            "This site requires WebView2 support. Install it with: python -m pip install -e .[browser]"
        ) from exc

    captured: dict[str, object] = {}
    capture_started = threading.Event()
    session_monitor_started = threading.Event()
    original_handler = edgechromium.EdgeChrome.on_download_starting

    def complete_capture(window: object, download_url: str, filename: str | None = None) -> None:
        if capture_started.is_set():
            return
        capture_started.set()
        captured["url"] = download_url
        if filename:
            captured["filename"] = Path(filename).name

        def collect_session() -> None:
            time.sleep(0.2)
            window.destroy()

        threading.Thread(target=collect_session, daemon=True).start()

    def fail_capture(window: object, message: str) -> None:
        if capture_started.is_set():
            return
        capture_started.set()
        captured["error"] = message
        threading.Thread(target=window.destroy, daemon=True).start()

    def on_download_starting(self: object, sender: object, args: object) -> None:
        args.Handled = True  # type: ignore[attr-defined]
        args.Cancel = True  # type: ignore[attr-defined]
        operation = args.DownloadOperation  # type: ignore[attr-defined]
        complete_capture(
            self.pywebview_window,  # type: ignore[attr-defined]
            str(operation.Uri),
            Path(str(args.ResultFilePath)).name,  # type: ignore[attr-defined]
        )

    edgechromium.EdgeChrome.on_download_starting = on_download_starting
    try:
        webview.settings["ALLOW_DOWNLOADS"] = True
        window = webview.create_window(
            "LinkFetch — complete the verification and click Download",
            url,
            width=760,
            height=820,
            resizable=True,
            text_select=True,
        )

        def on_response(response: object) -> None:
            if 520 <= int(response.status_code) <= 526:
                fail_capture(
                    window,
                    f"The origin server returned Cloudflare {response.status_code}; "
                    "the file host is temporarily unavailable.",
                )
                return
            headers = {str(key).lower(): str(value) for key, value in response.headers.items()}
            disposition = headers.get("content-disposition", "").lower()
            content_type = headers.get("content-type", "").lower().split(";", 1)[0]
            is_file = "attachment" in disposition or content_type in {
                "application/octet-stream",
                "application/zip",
                "application/x-rar-compressed",
                "application/vnd.rar",
            }
            if not is_file:
                return
            match = re.search(r"filename\*?=(?:UTF-8''|\")?([^\";]+)", disposition, re.IGNORECASE)
            filename = match.group(1).strip() if match else None
            complete_capture(window, str(response.url), filename)

        window.events.response_received += on_response

        def start_session_monitor() -> None:
            if session_monitor_started.is_set():
                return
            session_monitor_started.set()

            def monitor() -> None:
                while not capture_started.is_set():
                    try:
                        captured["user_agent"] = window.evaluate_js("navigator.userAgent")
                        cookies: list[tuple[str, str]] = []
                        for jar in window.get_cookies() or []:
                            cookies.extend((name, morsel.value) for name, morsel in jar.items())
                        captured["cookies"] = cookies
                    except Exception:
                        pass
                    time.sleep(0.25)

            threading.Thread(target=monitor, daemon=True).start()

        window.events.loaded += start_session_monitor

        if button_selector:
            selector = json.dumps(button_selector)

            def automate_after_verification() -> None:
                window.run_js(
                    f"""
                    (() => {{
                      if (window.__linkfetchAutomation) return;
                      window.__linkfetchAutomation = setInterval(() => {{
                        const challenge = document.querySelector(
                          'input[name="cf-turnstile-response"], textarea[name="cf-turnstile-response"]'
                        );
                        if (challenge && !challenge.value) return;
                        const button = document.querySelector({selector});
                        if (!button || button.dataset.linkfetchClicked === 'true') return;
                        if (button.disabled || button.getAttribute('aria-disabled') === 'true') return;
                        if (button.tagName === 'A') {{
                          const href = button.getAttribute('href');
                          if (!href || href === '#') return;
                        }}
                        button.dataset.linkfetchClicked = 'true';
                        button.click();
                      }}, 400);
                    }})();
                    """
                )

            window.events.loaded += automate_after_verification
        webview.start(
            gui="edgechromium",
            debug=False,
            private_mode=True,
            storage_path=str(Path(os.environ.get("LOCALAPPDATA", Path.home())) / "LinkFetch" / "webview2"),
        )
    finally:
        edgechromium.EdgeChrome.on_download_starting = original_handler

    if captured.get("error"):
        raise WebViewCaptureError(str(captured["error"]))
    download_url = captured.get("url")
    if not isinstance(download_url, str):
        raise WebViewCaptureError("The window was closed before a download started.")
    cookie_values = captured.get("cookies")
    cookie_header = ""
    if isinstance(cookie_values, list):
        cookie_header = "; ".join(
            f"{name}={value}"
            for name, value in cookie_values
            if isinstance(name, str) and isinstance(value, str)
        )
    headers = {"Referer": url}
    if cookie_header:
        headers["Cookie"] = cookie_header
    user_agent = captured.get("user_agent")
    if isinstance(user_agent, str) and user_agent:
        headers["User-Agent"] = user_agent
    filename = captured.get("filename")
    return ResolvedDownload(
        url=download_url,
        filename=filename if isinstance(filename, str) and filename else None,
        headers=headers,
    )
