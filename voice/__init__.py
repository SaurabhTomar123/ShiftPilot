"""M5: browser voice channel (Pipecat). Install extras: pip install -e ".[voice]"

Plan (voice/pipeline.py):
    SmallWebRTCTransport -> SileroVAD -> DeepgramSTT (nova, streaming)
    -> AgentProcessor (wraps agent.entrypoint.run_turn; speak a filler line if a tool takes > 700 ms)
    -> CartesiaTTS (streaming) -> transport.output()
Requirements: barge-in on, read back any pending action and require a spoken "yes" before calling
/actions/{id}/approve, log per-stage latency (stt, llm first token, tools, tts first byte) to
Langfuse. Target p50 <= 1.2 s, p95 <= 2 s from end of speech to first audio.
"""
