from core.voice_conversation import VoiceConversationMode


def test_push_to_talk_gates_audio_capture():
    voice = VoiceConversationMode()

    assert not voice.should_capture_audio(muted=False, mica_speaking=False)

    voice.configure(input_mode="push_to_talk", push_to_talk_active=True)
    assert voice.should_capture_audio(muted=False, mica_speaking=False)
    assert not voice.should_capture_audio(muted=True, mica_speaking=False)
    assert not voice.should_capture_audio(muted=False, mica_speaking=True)


def test_open_mic_and_wakeword_allow_capture_when_available():
    voice = VoiceConversationMode()

    voice.configure(input_mode="open_mic", push_to_talk_active=False)
    assert voice.should_capture_audio(muted=False, mica_speaking=False)

    voice.configure(input_mode="wakeword", wakeword_enabled=True)
    assert voice.should_capture_audio(muted=False, mica_speaking=False)
    assert voice.snapshot()["wakeword_enabled"] is True


def test_transcript_snapshot_and_interrupt_are_recorded():
    voice = VoiceConversationMode()

    voice.record_transcript("user", "mach das licht an")
    voice.record_transcript("assistant", "Das Licht ist an.")
    interrupted = voice.request_interrupt()

    assert interrupted["last_transcript"] == "mach das licht an"
    assert interrupted["last_response"] == "Das Licht ist an."
    assert interrupted["last_interrupt_at"]
    assert interrupted["turns"][-1]["role"] == "system"
