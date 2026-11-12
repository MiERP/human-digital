# Implementation plan: animated companion avatar

## Architecture decisions

- Reuse `ConnectionState`, `RobotEmotion`, and audio amplitude already received by the Android client.
- Use a deterministic visual-state model for tests; Compose animates the resulting values.
- Render expressive eyes, ear glows, chest glow, and hand-wave overlays on top of the transparent avatar. This avoids mismatched AI-generated poses and preserves the chosen robot's identity.

## Tasks

### 1. Define visual-state mapping

- Acceptance: pure functions map connection/emotion/audio data to eye treatment, light palette, light energy, and gesture strength; sleep is still.
- Verify: focused unit tests.
- Files: `CompanionMotion.kt`, `CompanionMotionTest.kt`.

### 2. Render face and lights

- Acceptance: avatar displays eyes/mouth and ear/chest light layers that interpolate according to the visual state.
- Verify: build plus device screenshot in idle and sleep states.
- Files: `DoraemonAvatar.kt`.

### 3. Add alternating hand gestures

- Acceptance: speaking produces a gentle left/right alternating hand-wave, while listening/thinking/sleeping do not wave.
- Verify: unit tests for phase values plus two device frames during speech.
- Files: `CompanionMotion.kt`, `DoraemonAvatar.kt`, `CompanionMotionTest.kt`.

### 4. Device validation and review

- Acceptance: no opaque square, no runtime error, and all tests/builds pass.
- Verify: install debug APK on SM-A235F and inspect screenshots/logcat.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Whole-image asset cannot physically separate limbs | Use carefully clipped, subtle overlays for a conversational hand-wave rather than rotating the entire body. |
| Bright effects distract children | Cap light alpha and use gentle easing; no strobes. |
| Emotion values vary by backend | Treat unknown values as neutral. |
