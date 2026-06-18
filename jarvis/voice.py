"""Optional voice I/O — completely free / offline-capable.

- TTS: ``pyttsx3`` uses the OS speech engine (SAPI5 on Windows). No cloud, no key.
- STT: ``SpeechRecognition``. Use the offline Sphinx engine for a fully free
  pipeline, or Google's free web endpoint (no key) if you prefer accuracy.

Everything is guarded so importing JARVIS never requires these packages.
"""

from __future__ import annotations

from jarvis.utils.logging import get_logger

logger = get_logger("jarvis.voice")


class Voice:
    def __init__(self, stt_engine: str = "google", rate: int = 185) -> None:
        self.stt_engine = stt_engine
        self._tts = None
        self._recognizer = None
        self._mic = None
        self._init_tts(rate)
        self._init_stt()

    @property
    def tts_available(self) -> bool:
        return self._tts is not None

    @property
    def stt_available(self) -> bool:
        return self._recognizer is not None and self._mic is not None

    def _init_tts(self, rate: int) -> None:
        try:
            import pyttsx3

            self._tts = pyttsx3.init()
            self._tts.setProperty("rate", rate)
        except Exception as exc:  # noqa: BLE001
            logger.info("TTS unavailable (pip install pyttsx3): %s", exc)

    def _init_stt(self) -> None:
        try:
            import speech_recognition as sr

            self._recognizer = sr.Recognizer()
            self._mic = sr.Microphone()
        except Exception as exc:  # noqa: BLE001
            logger.info(
                "STT unavailable (pip install SpeechRecognition pyaudio): %s", exc
            )

    def speak(self, text: str) -> None:
        if not self._tts:
            return
        self._tts.say(text)
        self._tts.runAndWait()

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
