# Companion experience: a friend who grows with the child

## Objective

The child returns to talk with a consistent AI character who listens, jokes, can disagree gently, changes mood in context, and remembers shared moments. English practice happens when it fits the conversation; a child's story or feeling takes priority over a lesson prompt.

## Behavioral contract

- Each companion preset has stable personality traits and a conversational style beyond its name, voice, and appearance.
- The companion acknowledges what the child said before changing topic. It may offer a different opinion with a reason, accept a good counterargument, and tease playfully without shaming or escalating conflict.
- The companion does not force a question or an English exercise at the end of every turn. It uses a small speaking invitation when it fits the child's interest and stops when the child declines.
- A meaningful shared event can be saved as a short episodic memory. Future sessions may recall it naturally and accurately. Transient small talk and sensitive details are not promoted to shared memory.
- Mood can evolve during a session and carries into a later session after time-based recovery. It does not reset to the same happy state on every connection.
- The character is transparent that it is an AI companion if asked and does not claim to be a human or demand exclusive attachment.

## Session continuity

- A scheduled study-duration nudge does not terminate the live conversation.
- The app plays all queued farewell audio before switching to sleep.
- A failed profile reset leaves the parent on the current screen with an actionable error.
- A newly agreed study plan updates the device reminder without requiring the parent to open another screen. Disabled reminders stay off; enabled reminders are restored after reboot, subject to Android notification permission.

## Implementation and verification

- Backend: `personas.py` and `main.py` own the persona and live-session instructions; `memory_manager.py` stores shared moments; `emotion_engine.py` stores mood. Backend tests exercise persistence and session behavior without a Gemini connection.
- Android: `MainActivity.kt`, `AudioPlayer.kt`, and `ReminderScheduler.kt` own session and reminder UX. `gradlew.bat assembleDebug --offline` must pass.
- Acceptance: the backend test suite passes, the Android debug build passes, and the four continuity paths above can be traced end to end.

This is a first implementation slice. It does not introduce a full curriculum or autonomous long-term relationship planner.
