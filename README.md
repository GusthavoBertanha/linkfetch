# LinkFetch

LinkFetch is a command-line downloader that resolves public file-hosting links
and saves one download per process. It supports retries, HTTP range requests,
atomic completion, and resumable `.part` files.

The project uses small, isolated host adapters. Each adapter resolves an
official download flow and hands the resulting URL and session data to the same
resumable transfer engine.

## Features

- One URL per process, making parallel downloads easy to manage.
- Automatic retries with exponential backoff.
- Resume support when the origin accepts HTTP `Range` requests.
- Atomic rename after a transfer completes.
- Human-in-the-loop browser window for supported verification pages.
- Native decryption of public MEGA file and folder links.
- Refuses to save an HTML page as if it were a file.

## Requirements

- Python 3.10 or newer.
- Windows 10 or newer for the embedded WebView2 verification flow.
- Microsoft Edge WebView2 Runtime for hosts that require that flow.

## Installation

```powershell
python -m pip install -e .
```

Install the optional browser components when you need AkiraBox, VikingFile, or
BuzzHeavier support:

```powershell
python -m pip install -e ".[browser]"
```

## Usage

Download into the current directory:

```powershell
linkfetch "https://example.com/file.zip"
```

Choose a destination directory:

```powershell
linkfetch "https://example.com/file.zip" --output "D:\Downloads"
```

Inspect how a URL is classified without downloading it:

```powershell
linkfetch "https://mega.nz/file/ID#KEY" --resolve-only
```

Available options:

```text
--output PATH       destination directory; defaults to the current directory
--name NAME         override the final file name
--retries N         retry count after a failure; defaults to 5
--timeout SECONDS   network timeout; defaults to 30 seconds
--no-resume         restart instead of continuing a partial file
--quiet             hide progress output
--resolve-only      resolve and display the destination without downloading
```

Press `Ctrl+C` to stop a transfer. LinkFetch preserves the `.part` file and its
`.linkfetch.json` state so the next run can continue it.

## Host support

### Validated with a real partial transfer

Integration checks fetched only a small byte range and stopped before saving a
complete hosted file.

| Host | Resolution method |
| --- | --- |
| Direct HTTP/HTTPS | Generic resumable transfer engine |
| MediaFire | Official download button and session cookies |
| PixelDrain | Public file API |
| AkiraBox | Embedded WebView2 after human verification |
| VikingFile | Embedded WebView2 after human verification |
| MEGA | Public API, range requests, and local AES decryption |
| Google Drive | Public file content endpoint |
| Archive.org | Generic resumable transfer engine |
| FileCrypt | Human verification, isolated file-row selection, and delegation to the final host adapter |

### Implemented, pending complete service validation

| Host | Current limitation |
| --- | --- |
| 1fichier | The official free flow worked, but no free slot was available during testing |
| BuzzHeavier | Its file origin returned Cloudflare 521 during testing |

### Recognized but unsupported

Qiwi, Ranoz, Rootz, Transfer.it, LetsUpload, and Uptobox are detected
so LinkFetch can return a useful diagnostic. They are not advertised as working
download adapters.

## Browser verification

Some hosts require a person to complete a verification challenge. LinkFetch
opens an embedded WebView2 window for that step, waits for the official download
action, cancels the browser-managed transfer, and continues through its own
resumable engine. LinkFetch does not solve CAPTCHAs automatically.

For FileCrypt, LinkFetch accepts single-file containers. It blocks advertising
pop-ups and browser downloads, follows the selected file's internal `/Link/`
route, captures the final host, and passes that URL to the matching adapter.
Containers with multiple file rows are reported as unsupported for now.

## Development

```powershell
python -m unittest discover -s tests -v
```

Live host checks are separate from unit tests because public links expire and
external services change independently of this repository.

## Responsible use

Only download content you are authorized to access. Follow the origin service's
terms, rate limits, and applicable law. LinkFetch contains no hosted-file index,
search catalog, credentials, or copyrighted downloads.

## License

LinkFetch is available under the [MIT License](LICENSE).
