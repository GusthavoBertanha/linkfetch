from __future__ import annotations

import base64
import json
import os
import secrets
import struct
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from Crypto.Cipher import AES
from Crypto.Util import Counter

from linkfetch.downloader import CHUNK_SIZE, USER_AGENT, DownloadError, compatible_tls_context, safe_filename

API = "https://g.api.mega.co.nz/cs"


def _b64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _api(commands: list[dict[str, object]], *, folder: str | None = None, timeout: float = 30) -> list[object]:
    query = f"?id={secrets.randbelow(2**31)}" + (f"&n={folder}" if folder else "")
    request = Request(API + query, data=json.dumps(commands, separators=(",", ":")).encode(),
                      headers={"User-Agent": USER_AGENT, "Content-Type": "application/json"})
    with urlopen(request, timeout=timeout, context=compatible_tls_context()) as response:
        result = json.load(response)
    if not isinstance(result, list):
        raise DownloadError("Unexpected response from the MEGA API.")
    for entry in result:
        if isinstance(entry, int) and entry < 0:
            raise DownloadError(f"The MEGA API rejected the request (error {entry}).")
    return result


def _file_key(raw: bytes) -> tuple[bytes, bytes, bytes]:
    if len(raw) != 32:
        raise DownloadError("Invalid MEGA file key.")
    words = struct.unpack(">8I", raw)
    key = struct.pack(">4I", *(words[i] ^ words[i + 4] for i in range(4)))
    return key, struct.pack(">4I", words[4], words[5], 0, 0), struct.pack(">2I", words[6], words[7])


def _attrs(value: str, key: bytes) -> dict[str, object]:
    raw = AES.new(key, AES.MODE_CBC, iv=b"\0" * 16).decrypt(_b64(value)).rstrip(b"\0")
    if not raw.startswith(b"MEGA{"):
        raise DownloadError("The MEGA link key does not match the file.")
    try:
        return json.loads(raw[4:].decode())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DownloadError("Corrupt MEGA attributes.") from exc


@dataclass(slots=True)
class MegaFile:
    handle: str
    name: str
    size: int
    key: bytes
    iv: bytes
    folder: str | None = None
    relative: Path = Path()


def _parse(url: str) -> tuple[str, str, bytes]:
    parsed = urlsplit(url)
    parts = parsed.path.strip("/").split("/")
    if len(parts) != 2 or parts[0] not in {"file", "folder"}:
        raise DownloadError("Unrecognized MEGA public-link format.")
    try:
        return parts[0], parts[1], _b64(parsed.fragment)
    except Exception as exc:
        raise DownloadError("Invalid MEGA link key.") from exc


def _single(handle: str, raw_key: bytes, timeout: float) -> MegaFile:
    key, iv, _ = _file_key(raw_key)
    info = _api([{"a": "g", "g": 1, "p": handle}], timeout=timeout)[0]
    if not isinstance(info, dict):
        raise DownloadError("MEGA did not return file metadata.")
    name = str(_attrs(str(info["at"]), key).get("n") or "download.bin")
    return MegaFile(handle, name, int(info["s"]), key, iv)


def _folder(handle: str, share_key: bytes, timeout: float) -> tuple[str, list[MegaFile]]:
    if len(share_key) != 16:
        raise DownloadError("Invalid MEGA folder key.")
    response = _api([{"a": "f", "c": 1, "r": 1}], folder=handle, timeout=timeout)[0]
    if not isinstance(response, dict) or not isinstance(response.get("f"), list):
        raise DownloadError("MEGA did not return the folder contents.")
    nodes = {str(n["h"]): n for n in response["f"] if isinstance(n, dict) and "h" in n}
    names: dict[str, str] = {}
    keys: dict[str, bytes] = {}
    root_name = f"mega-{handle}"
    for node_id, node in nodes.items():
        try:
            encrypted = _b64(str(node.get("k", "")).split(":")[-1])
            node_key = AES.new(share_key, AES.MODE_ECB).decrypt(encrypted)
            attr_key = node_key if int(node.get("t", 0)) else _file_key(node_key)[0]
            names[node_id] = safe_filename(str(_attrs(str(node["a"]), attr_key).get("n") or node_id))
            keys[node_id] = node_key
            if int(node.get("t", 0)) == 2:
                root_name = names[node_id]
        except (KeyError, ValueError, DownloadError):
            continue
    def relative(node_id: str) -> Path:
        result: list[str] = []
        parent = str(nodes[node_id].get("p", ""))
        while parent in nodes and int(nodes[parent].get("t", 0)) != 2:
            result.append(names.get(parent, parent))
            parent = str(nodes[parent].get("p", ""))
        return Path(*reversed(result))
    files: list[MegaFile] = []
    for node_id, node in nodes.items():
        if int(node.get("t", 0)) == 0 and node_id in keys:
            key, iv, _ = _file_key(keys[node_id])
            files.append(MegaFile(node_id, names[node_id], int(node["s"]), key, iv, handle, relative(node_id)))
    if not files:
        raise DownloadError("The public MEGA folder contains no accessible files.")
    return root_name, files


def _source(file: MegaFile, timeout: float) -> str:
    command = {"a": "g", "g": 1, "n" if file.folder else "p": file.handle}
    info = _api([command], folder=file.folder, timeout=timeout)[0]
    if not isinstance(info, dict) or not isinstance(info.get("g"), str):
        raise DownloadError("MEGA did not provide a temporary file URL.")
    return info["g"]


def _download_file(owner, file: MegaFile, destination: Path, override: str | None = None) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    name = safe_filename(override or file.name)
    part = destination / f"{name}.part"
    state = destination / f"{name}.linkfetch.json"
    offset = part.stat().st_size if owner.resume and part.exists() else 0
    if offset > file.size:
        offset = 0
    offset -= offset % 16
    if part.exists() and part.stat().st_size != offset:
        with part.open("r+b") as stream:
            stream.truncate(offset)
    source = _source(file, owner.timeout)
    headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "identity"}
    if offset:
        headers["Range"] = f"bytes={offset}-"
    metadata = {"url": source, "filename": name, "downloaded": offset, "total": file.size, "updated_at": time.time()}
    owner._write_state(state, metadata)
    cipher = AES.new(file.key, AES.MODE_CTR,
                     counter=Counter.new(128, initial_value=int.from_bytes(file.iv, "big") + offset // 16))
    downloaded = offset
    started = last_update = time.monotonic()
    with urlopen(Request(source, headers=headers), timeout=owner.timeout,
                 context=compatible_tls_context()) as response, part.open("ab" if offset else "wb") as target:
        if offset and getattr(response, "status", response.getcode()) != 206:
            raise DownloadError("MEGA rejected the resume request; remove the .part file and try again.")
        while chunk := response.read(CHUNK_SIZE):
            plain = cipher.decrypt(chunk)
            target.write(plain)
            downloaded += len(plain)
            now = time.monotonic()
            if now - last_update >= .5:
                metadata.update(downloaded=downloaded, updated_at=time.time())
                owner._write_state(state, metadata)
                owner._progress(downloaded, file.size, now - started)
                last_update = now
        target.flush()
        os.fsync(target.fileno())
    if downloaded != file.size:
        raise DownloadError(f"Incomplete MEGA transfer: {downloaded} of {file.size} bytes")
    final = destination / name
    if final.exists():
        raise DownloadError(f"The final file already exists: {final}")
    part.replace(final)
    state.unlink(missing_ok=True)
    owner._progress(downloaded, file.size, max(time.monotonic() - started, .001), done=True)
    return final


def download_public_link(owner, url: str, name: str | None = None) -> Path:
    kind, handle, key = _parse(url)
    if kind == "file":
        return _download_file(owner, _single(handle, key, owner.timeout), owner.output, name)
    root_name, files = _folder(handle, key, owner.timeout)
    root = owner.output / safe_filename(name or root_name)
    owner._print(f"MEGA folder: {len(files)} file(s).")
    for index, file in enumerate(files, 1):
        owner._print(f"[{index}/{len(files)}] {file.name}")
        destination = root / file.relative
        completed = destination / safe_filename(file.name)
        if completed.is_file() and completed.stat().st_size == file.size:
            owner._print("File already completed; skipping.")
            continue
        _download_file(owner, file, destination)
    return root
