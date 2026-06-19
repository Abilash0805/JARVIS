"""Optional voice I/O — completely free / offline-capable.

- TTS: on Windows we drive the built-in **System.Speech** synthesizer via
  PowerShell, which reliably speaks on every call. ``pyttsx3`` is used as a
  fallback / on other OSes. (Reusing a single pyttsx3 engine is what causes the
  common "speaks only once" bug, so we avoid it.)
- STT: ``SpeechRecognition``. Use the offline Sphinx engine for a fully free
  pipeline, or Google's free web endpoint (no key) if you prefer accuracy.

Everything is guarded so importing JARVIS never requires these packages.
"""

from __future__ import annotations

import base64
import platform
import shutil
import subprocess

from jarvis.utils.logging import get_logger

logger = get_logger("jarvis.voice")


class Voice:
    def __init__(self, stt_engine: str = "google", rate: int = 185) -> None:
        self.stt_engine = stt_engine
        self.rate = rate
        self._recognizer = None
        self._mic = None
        self._tts_backend = self._detect_tts()
        self._init_stt()
        if self._tts_backend:
            logger.info("TTS backend: %s", self._tts_backend)

    @property
    def tts_available(self) -> bool:
        return self._tts_backend is not None

    @property
    def tts_backend(self) -> str | None:
        return self._tts_backend

    @property
    def stt_available(self) -> bool:
        return self._recognizer is not None and self._mic is not None

    # --- TTS backend detection -------------------------------------------
    def _detect_tts(self) -> str | None:
        # Windows: prefer System.Speech via PowerShell — rock solid for repeated
        # calls, no extra install.
        if platform.system() == "Windows" and (
            shutil.which("powershell") or shutil.which("powershell.exe")
        ):
            return "sapi"
        # Otherwise try pyttsx3 (espeak/nsss/sapi5 wrapper).
        try:
            import pyttsx3  # noqa: F401

            return "pyttsx3"
        except Exception as exc:  # noqa: BLE001
            logger.info("pyttsx3 unavailable (pip install pyttsx3): %s", exc)
        # Last resort: pyttsx3 on Windows even without powershell.
        return None

    def _init_stt(self) -> None:
        try:
            import speech_recognition as sr

            self._recognizer = sr.Recognizer()
            self._mic = sr.Microphone()
        except Exception as exc:  # noqa: BLE001
            logger.info(
                "STT unavailable (pip install SpeechRecognition pyaudio): %s", exc
            )

    # --- TTS ------------------------------------------------------------
    def speak(self, text: str) -> None:
        text = (text or "").strip()
        if not text or not self._tts_backend:
            return
        if self._tts_backend == "sapi":
            try:
                self._speak_sapi(text)
                return
            except Exception as exc:  # noqa: BLE001 - fall back to pyttsx3
                logger.warning("SAPI speak failed (%s); trying pyttsx3", exc)
        try:
            self._speak_pyttsx3(text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("TTS failed: %s", exc)

    def _speak_sapi(self, text: str) -> None:
        # Map our ~words-per-minute rate (≈185 default) to SAPI's -10..10 scale.
        sapi_rate = max(-10, min(10, round((self.rate - 185) / 15)))
        safe = text.replace("'", "''")
        script = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$s.Rate = {sapi_rate}; $s.Speak('{safe}')"
        )
        exe = shutil.which("powershell") or "powershell.exe"
        # JARVIS's replies routinely contain em dashes/curly quotes; passing
        # them through -Command as a raw command-line argument is at the
        # mercy of the console codepage and Windows argv quoting, which can
        # mangle or truncate them and make PowerShell fail to parse the
        # script (exit code 1). -EncodedCommand carries the script as
        # base64'd UTF-16LE text instead, sidestepping quoting/encoding
        # entirely.
        encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
        try:
            subprocess.run(
                [exe, "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                check=True,
                capture_output=True,
                timeout=120,
            )
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or b"").decode("utf-8", "replace").strip()
            raise RuntimeError(f"{exc}: {stderr}" if stderr else str(exc)) from exc

    def _speak_pyttsx3(self, text: str) -> None:
        import pyttsx3

        # Fresh engine per utterance avoids the "speaks once then stops" bug
        # caused by reusing a cached engine across runAndWait() calls.
        engine = pyttsx3.init()
        engine.setProperty("rate", self.rate)
        engine.say(text)
        engine.runAndWait()
        try:
            engine.stop()
        except Exception:  # noqa: BLE001
            pass

    def listen(self, timeout: float = 8.0, phrase_limit: float = 15.0) -> str:
        """Capture one utterance from the mic and return the transcript."""
        if not self.stt_available:
            raise RuntimeError("speech recognition not available")
        import speech_recognition as sr

        with self._mic as source:  # type: ignore[union-attr]
            self._recognizer.adjust_for_ambient_noise(source, duration=0.4)
            audio = self._recognizer.listen(
                source, timeout=timeout, phrase_time_limit=phrase_limit
            )
        try:
            if self.stt_engine == "sphinx":
                return self._recognizer.recognize_sphinx(audio)  # offline, free
            return self._recognizer.recognize_google(audio)  # free web endpoint
        except sr.UnknownValueError:
            return ""
        except sr.RequestError as exc:
            raise RuntimeError(f"speech recognition failed: {exc}")

    def run_wake_loop(
        self,
        on_command,
        wake_word: str = "jarvis",
        should_stop=None,
    ) -> None:
        """Listen continuously; on hearing the wake word, capture a command.

        If the wake-word utterance also contains the command ("jarvis, what
        time is it"), that text is used directly; otherwise JARVIS prompts for
        the command. ``on_command(text)`` handles each captured command;
        ``should_stop()`` (optional) ends the loop when it returns True.
        """
        if not self.stt_available:
            raise RuntimeError("speech recognition not available")
        wake = wake_word.lower()
        while not (should_stop and should_stop()):
            try:
                heard = self.listen(timeout=None, phrase_limit=6.0).lower()
            except RuntimeError:
                continue
            if wake not in heard:
                continue
            remainder = heard.split(wake, 1)[1].strip(" ,.").strip()
            if remainder:
                command = remainder
            else:
                self.speak("Yes?")
                command = self.listen(timeout=8.0, phrase_limit=15.0)
            if command.strip():
                on_command(command.strip())


def _selftest(argv: list[str]) -> int:
    """`python -m jarvis.voice ["text to speak"]` — verify TTS/STT quickly."""
    v = Voice()
    print(f"TTS backend: {v.tts_backend}  (available={v.tts_available})")
    print(f"STT available: {v.stt_available}")
    text = " ".join(a for a in argv if not a.startswith("-")) or (
        "Hello, this is JARVIS. Voice output is working."
    )
    if v.tts_available:
        print(f"speaking: {text!r}")
        v.speak(text)
        v.speak("And this is a second sentence, to prove repeated speech works.")
        print("done — if you heard two sentences, talkback is fixed.")
    else:
        print("No TTS backend. On Windows ensure PowerShell is on PATH, "
              "or `pip install pyttsx3`.")
        return 1
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(_selftest(sys.argv[1:]))
