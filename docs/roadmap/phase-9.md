# PHASE 9 — Voice (extension, added on 2026-08-27)

The voice agents segment is rising fast in 2026 job postings and the testbench had no
audio component. Same logic as everything else: **we plug into the existing system, we
measure**.

Real-time pipeline STT → existing agent → TTS, exposed by the current API: bidirectional
audio streaming, barge-in (the user interrupts the agent), handling of silence and
turn-taking. Perceived latency becomes the central topic: TTFT becomes a
**time-to-first-audio**, broken down by step (STT, agent, TTS) with the observability harness
of phase 5. Cost per minute of conversation, compared with the cost per text request.
Graceful degradation to text when audio fails.

**Evaluation datasets** to verify at the start of the phase (same protocol as phase 0:
availability, size, license) — candidates: VoiceBench and equivalents; failing that, audio
replay of the questions of the existing text datasets via TTS, with the contamination of this
loop documented.

**Notebooks**: (1) where the latency of a voice agent comes from — the millisecond-by-millisecond
breakdown; (2) evaluating an agent you listen to: what changes when the output is no longer
text.

**At the end of the phase**: GO/NO-GO decision on phase 10.
