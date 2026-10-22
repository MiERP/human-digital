# Companion experience: a friend who grows with the child

## Objective

The child returns to talk with a consistent AI character who listens, jokes, can disagree gently, changes mood in context, and remembers shared moments. Conversation is the product; learning is a by-product of curiosity, never the agenda of a turn. A child's story or feeling takes priority over a lesson prompt.

## Behavioral contract

- Each companion preset has stable personality traits and a conversational style beyond its name, voice, and appearance.
- The companion acknowledges what the child said before changing topic. It may offer a different opinion with a reason, accept a good counterargument, and tease playfully without shaming or escalating conflict.
- The companion is proactive: after a lull it may open a topic, share a small thought, or ask about the day. It backs off when the child does not answer instead of repeating the invitation, and it never turns an opening into a quiz or a lesson.
- The companion does not force a question or an English exercise at the end of every turn. It uses a small speaking invitation when it fits the child's interest and stops when the child declines.
- Learning stays opt-in. With no agreed study plan, the prompt contains no learning block at all; a plan is mentioned only when the child or parent raises it.
- The companion does not recycle a sentence, story detail, compliment, memory, or filler within a session. Reconnect does not replay the opening greeting.
- A meaningful shared event can be saved as a short episodic memory. Future sessions may recall it naturally and accurately, without reciting it verbatim. Transient small talk and sensitive details are not promoted to shared memory.
- Mood can evolve during a session and carries into a later session after time-based recovery. It does not reset to the same happy state on every connection.
- The character is transparent that it is an AI companion if asked and does not claim to be a human or demand exclusive attachment.

## Session continuity

- A proactive companionship nudge is throttled and backed off (`PROACTIVE_IDLE_SECONDS`, `PROACTIVE_MAX_UNANSWERED`, `PROACTIVE_MAX_PER_SESSION`) and never ends the live conversation.
- An automatic reconnect resumes the same Gemini conversation when a valid resumption handle is available, using the API key that issued it. A stale handle is cleared before retrying a fresh connection; no second opening greeting is sent for a resumed session.
- When the child interrupts, queued and in-flight audio from the cancelled turn is dropped, so the previous sentence does not resume before the new answer.
- The app plays all queued farewell audio before switching to sleep.
- A failed profile reset leaves the parent on the current screen with an actionable error.
- A newly agreed study plan updates the device reminder without requiring the parent to open another screen. Disabled reminders stay off; enabled reminders are restored after reboot, subject to Android notification permission.

## Implementation and verification

- Backend: `personas.py` and `main.py` own the persona, proactive companionship, and live-session instructions; `memory_manager.py` stores shared moments and builds the opt-in learning block; `emotion_engine.py` stores mood. Backend tests exercise persistence and session behavior without a Gemini connection.
- Android: `MainActivity.kt`, `AudioPlayer.kt`, and `ReminderScheduler.kt` own session, interruption, and reminder UX. `AudioPlayer` exposes `beginInterruption()` for barge-in; `GeminiLiveClient` guards reconnects with a connection generation and sends `is_reconnect` in `auth_init`. `gradlew.bat assembleDebug --offline` must pass.
- Acceptance: the backend test suite passes, the Android debug build passes, one silent-turn nudge is observed end to end, and the continuity paths above can be traced end to end.

This is a first implementation slice. It does not introduce a full curriculum or autonomous long-term relationship planner.
