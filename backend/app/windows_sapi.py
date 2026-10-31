"""Bounded local Windows SAPI audio over an already-installed Python COM worker.

Utterance text is sent only over stdin. The fixed worker source is passed in
argv; learner text and generated audio are never put on process arguments/logs.
"""
from __future__ import annotations

import base64
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import uuid

MAX_TEXT_LENGTH = 300
MAX_WAV_BYTES = 2 * 1024 * 1024
WORKER_START_TIMEOUT_SECONDS = 10
SYNTHESIS_TIMEOUT_SECONDS = 8
SAPI_VERSION = "windows-sapi-com-v1"


def is_english_sapi_language(value: str) -> bool:
    """Accept any SAPI locale whose Windows primary language is English (0x09)."""
    if not isinstance(value, str):
        return False
    for language_id in re.findall(r"[0-9A-Fa-f]+", value):
        try:
            if int(language_id, 16) & 0x3FF == 0x09:
                return True
        except ValueError:
            continue
    return False


def first_english_sapi_language_index(values: list[str]) -> int | None:
    """Return the first installed English locale or None when no English exists."""
    return next((index for index, value in enumerate(values) if is_english_sapi_language(value)), None)

_WORKER_SCRIPT = r'''import base64, io, json, re, sys, wave
import pythoncom, win32com.client
voice = None
try:
    pythoncom.CoInitialize()
    voice = win32com.client.Dispatch("SAPI.SpVoice")
    tokens = voice.GetVoices()
    english = []
    for index in range(tokens.Count):
        token = tokens.Item(index)
        language = token.GetAttribute("Language")
        if any((int(value, 16) & 0x3ff) == 0x09 for value in re.findall(r"[0-9A-Fa-f]+", language)):
            english.append(token)
    if not english:
        print(json.dumps({"ready": False, "error": "no_local_english_voice"}), flush=True)
        raise SystemExit(0)
    token = english[0]
    voice.Voice = token
    voice_name = token.GetDescription()
    print(json.dumps({"ready": True, "voice": voice_name}), flush=True)
    for line in sys.stdin:
        request = {}
        try:
            request = json.loads(line)
            if request.get("stop") is True:
                break
            stream = win32com.client.Dispatch("SAPI.SpMemoryStream")
            stream.Format.Type = 22
            voice.AudioOutputStream = stream
            voice.Speak(request["text"], 16)
            raw_audio = bytes(stream.GetData())
            # Keep the final RIFF container (44-byte header) within MAX_WAV_BYTES.
            if not raw_audio or len(raw_audio) > 2097100:
                reply = {"id": request.get("id"), "error": "audio_size_invalid"}
            else:
                output = io.BytesIO()
                with wave.open(output, "wb") as audio:
                    audio.setnchannels(1)
                    audio.setsampwidth(2)
                    audio.setframerate(22050)
                    audio.writeframes(raw_audio)
                wav = output.getvalue()
                reply = {"id": request.get("id"), "wav": base64.b64encode(wav).decode("ascii")}
        except Exception:
            reply = {"id": request.get("id") if isinstance(request, dict) else None,
                     "error": "local_synthesis_failed"}
        print(json.dumps(reply, separators=(",", ":")), flush=True)
except Exception:
    print(json.dumps({"ready": False, "error": "local_speech_unavailable"}), flush=True)
finally:
    try:
        pythoncom.CoUninitialize()
    except Exception:
        pass
'''


class WindowsSapiUnavailable(RuntimeError):
    pass


class WindowsSapiBusy(RuntimeError):
    pass


class WindowsSapiTimeout(RuntimeError):
    pass


def _python_candidates() -> list[str]:
    candidates: list[str] = []
    if sys.executable.lower().endswith("python.exe"):
        candidates.append(sys.executable)
    local = os.environ.get("LOCALAPPDATA")
    if local:
        root = os.path.join(local, "Programs", "Python")
        try:
            for entry in sorted(os.listdir(root), reverse=True):
                candidate = os.path.join(root, entry, "python.exe")
                if entry.lower().startswith("python") and os.path.isfile(candidate) and candidate not in candidates:
                    candidates.append(candidate)
        except OSError:
            pass
    for name in ("python.exe", "python"):
        path = shutil.which(name)
        if path and path not in candidates:
            candidates.append(path)
    return candidates


def _worker_executable() -> str | None:
    if os.name != "nt":
        return None
    for executable in _python_candidates():
        try:
            probe = subprocess.run([executable, "-c", "import pythoncom, win32com.client"],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, timeout=3, check=False,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if probe.returncode == 0:
                return executable
        except Exception:
            continue
    return None


class WindowsSapiWorker:
    """One lazily started COM process with one in-flight utterance at a time."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None
        self._responses: queue.Queue[dict | None] | None = None
        self._ready = False
        self.voice_name: str | None = None

    @staticmethod
    def available() -> bool:
        return _worker_executable() is not None

    def _terminate_locked(self) -> None:
        process = self._process
        self._process = None
        self._responses = None
        self._ready = False
        self.voice_name = None
        if process is None:
            return
        try:
            if process.stdin and process.poll() is None:
                process.stdin.write(json.dumps({"stop": True}) + "\n")
                process.stdin.flush()
        except Exception:
            pass
        try:
            process.wait(timeout=0.4)
        except Exception:
            try:
                process.terminate()
                process.wait(timeout=0.4)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
        for stream in (process.stdin, process.stdout, process.stderr):
            try:
                if stream:
                    stream.close()
            except Exception:
                pass

    @staticmethod
    def _read_responses(process: subprocess.Popen[str], responses: queue.Queue[dict | None]) -> None:
        try:
            assert process.stdout is not None
            for line in process.stdout:
                try:
                    responses.put(json.loads(line), timeout=0.2)
                except (json.JSONDecodeError, queue.Full):
                    responses.put({"error": "worker_protocol_error"}, timeout=0.2)
        except Exception:
            pass
        finally:
            try:
                responses.put(None, timeout=0.2)
            except queue.Full:
                pass

    def _start_locked(self) -> None:
        if self._process is not None and self._process.poll() is None and self._ready:
            return
        self._terminate_locked()
        executable = _worker_executable()
        if not executable:
            raise WindowsSapiUnavailable("A local Windows Python SAPI bridge is unavailable.")
        try:
            process = subprocess.Popen([executable, "-u", "-c", _WORKER_SCRIPT],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except Exception as error:
            raise WindowsSapiUnavailable("Local Windows speech could not start.") from error
        responses: queue.Queue[dict | None] = queue.Queue(maxsize=2)
        reader = threading.Thread(target=self._read_responses, args=(process, responses),
                                  name="windows-sapi-output", daemon=True)
        self._process, self._responses = process, responses
        reader.start()
        try:
            initial = responses.get(timeout=WORKER_START_TIMEOUT_SECONDS)
        except queue.Empty as error:
            self._terminate_locked()
            raise WindowsSapiTimeout("Local Windows speech startup timed out.") from error
        if not isinstance(initial, dict) or initial.get("ready") is not True:
            self._terminate_locked()
            raise WindowsSapiUnavailable("No local English Windows SAPI voice is available.")
        self.voice_name = str(initial.get("voice") or "Windows local English voice")
        self._ready = True

    def synthesize(self, text: str) -> bytes:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Speech text must contain audible characters.")
        if len(text) > MAX_TEXT_LENGTH:
            raise ValueError("Speech text exceeds the short local-audio limit.")
        if not self._lock.acquire(blocking=False):
            raise WindowsSapiBusy("A local voice request is already running.")
        try:
            self._start_locked()
            process, responses = self._process, self._responses
            if process is None or process.stdin is None or responses is None:
                raise WindowsSapiUnavailable("Windows local speech worker is unavailable.")
            request_id = uuid.uuid4().hex
            process.stdin.write(json.dumps({"id": request_id, "text": text}, ensure_ascii=True) + "\n")
            process.stdin.flush()
            try:
                response = responses.get(timeout=SYNTHESIS_TIMEOUT_SECONDS)
            except queue.Empty as error:
                self._terminate_locked()
                raise WindowsSapiTimeout("Local Windows speech exceeded its time limit.") from error
            if not isinstance(response, dict) or response.get("id") != request_id:
                self._terminate_locked()
                raise WindowsSapiUnavailable("Windows local speech returned an invalid response.")
            if not isinstance(response.get("wav"), str):
                raise WindowsSapiUnavailable("Windows local speech could not synthesize this excerpt.")
            try:
                wav = base64.b64decode(response["wav"], validate=True)
            except Exception as error:
                self._terminate_locked()
                raise WindowsSapiUnavailable("Windows local speech returned invalid audio.") from error
            if len(wav) > MAX_WAV_BYTES or len(wav) < 44 or wav[:4] != b"RIFF" or wav[8:12] != b"WAVE":
                self._terminate_locked()
                raise WindowsSapiUnavailable("Windows local speech returned invalid audio.")
            return wav
        finally:
            self._lock.release()

    def prepare(self) -> str:
        """Start the local worker and select its installed voice without speaking text."""
        if not self._lock.acquire(blocking=False):
            raise WindowsSapiBusy("A local voice request is already running.")
        try:
            self._start_locked()
            return self.voice_name or "Windows local English voice"
        finally:
            self._lock.release()

    def shutdown(self) -> None:
        with self._lock:
            self._terminate_locked()


_WORKER: WindowsSapiWorker | None = None
_WORKER_LOCK = threading.Lock()


def get_worker() -> WindowsSapiWorker:
    global _WORKER
    with _WORKER_LOCK:
        if _WORKER is None:
            _WORKER = WindowsSapiWorker()
        return _WORKER


def shutdown_worker() -> None:
    if _WORKER is not None:
        _WORKER.shutdown()
