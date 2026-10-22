# Robot gesture and chosen name

## Objective
During spoken replies, Robo's two arms lift and lower in alternating conversational gestures while its body remains fixed. Every visible robot name comes from the child's selected companion profile; the preset name is a fallback only when a preset was selected without a custom name. Legacy profiles with neither choice use the neutral name "Bạn Robot".

## Commands and structure
- Build: `cd android && .\gradlew.bat :app:assembleDebug --offline`
- Test: `cd android && .\gradlew.bat :app:testDebugUnitTest --offline`
- Android UI and motion: `android/app/src/main/java/com/example/digitalhuman/ui/`
- Profile fetching: `android/app/src/main/java/com/example/digitalhuman/network/`
- Unit tests: `android/app/src/test/java/`

## Style and testing
Keep gesture calculations deterministic in `companionMotion` and test low/high audio with both gesture phases. Resolve a custom name before the preset default, and test both cases. Verify the assembled app on a connected device when available.

## Boundaries
- Preserve the existing body sprite, voice pipeline, child profile, and all unrelated deployment files.
- Do not change server-side profile schema or add dependencies.
- Do not publish or deploy as part of this UI change.

## Success criteria
1. While speaking, each arm traverses a visible low-to-raised range, alternating rather than moving together.
2. Mouth continues following output audio amplitude; listening and sleeping do not perform speech gestures.
3. The chosen name appears before a voice session starts, remains correct after profile edits, and falls back to the selected preset name only when the child left it blank.
4. A legacy profile with no companion selection never presents the old Dora default as a chosen name.
5. During speech the shoulder-to-elbow segment moves only 3–4 degrees, without exposing a triangular armpit gap. Each forearm starts in a gently bent pose (internal elbow angle about 140–150 degrees) and pulses only another 5–10 degrees with voice amplitude, alternating up/down without sharp motion. The visible elbow joint is rounded rather than a triangular cut; both arms relax when not speaking.
