# Spec: Animated companion avatar

## Objective

Make the current transparent robot avatar feel responsive in live conversation. The companion must visibly communicate five states: listening, thinking, speaking, emotion-driven happy/sad/angry, and sleeping. It must do so without new dependencies or changes to the voice/backend protocol.

## Interaction design

| Trigger | Face and motion | Ear and chest lights |
| --- | --- | --- |
| Listening | Gentle hover; attentive eyes | Soft cyan pulse |
| Thinking | Slow hover; eyes glance upward | Slow violet scan |
| Speaking | Alternating hand-wave silhouette and audio-responsive bounce | Cyan light pulses with output amplitude |
| Happy / excited | Wide smiling eyes and brighter, faster glow | Warm gold-cyan sparkle pulse |
| Sad | Drooped eyes, slower hover | Desaturated blue, low intensity |
| Strict / displeased | Narrow eyes, stiller pose | Amber-red warning glow, never flashing rapidly |
| Sleeping / tired | Closed eyes; no arm gestures | Lights fade down and breathe slowly |

The robot will be treated as a whole transparent illustration, with composited Canvas effects rather than regenerating a different full image per frame. The arm illusion uses animated, clipped arm overlays derived from the current image, avoiding a dependency or a backend change.

## Tech stack and commands

- Kotlin + Jetpack Compose; Android minSdk 26.
- Build: `cd android && .\gradlew.bat assembleDebug`
- Test: `cd android && .\gradlew.bat testDebugUnitTest`
- Device verification: `C:\Android\sdk\platform-tools\adb.exe install -r app\build\outputs\apk\debug\app-debug.apk`

## Structure and style

- Avatar rendering: `android/app/src/main/java/com/example/digitalhuman/ui/DoraemonAvatar.kt`
- Deterministic state-to-motion values: `android/app/src/main/java/com/example/digitalhuman/ui/CompanionMotion.kt`
- Unit tests: `android/app/src/test/java/com/example/digitalhuman/ui/CompanionMotionTest.kt`
- Raster asset: `android/app/src/main/res/drawable-nodpi/robo_avatar.png`

Keep state mapping in pure Kotlin functions and keep Compose responsible only for interpolation and drawing. All lights must use alpha/scale motion, not strobe effects.

## Testing strategy

- Unit-test each state mapping: safe clamping, sleep stillness, emotion color, and voice-dependent energy.
- Build the debug APK after each complete slice.
- Install on the connected Samsung device and verify idle, speaking, and sleeping frames without a crash or opaque image background.

## Boundaries

- Always preserve the current voice protocol and accessible avatar description.
- Ask first before adding a library, changing the backend emotion schema, or replacing the companion's identity.
- Never add high-frequency flashing, modify unrelated deployment files, or publish/deploy the app.

## Success criteria

1. The avatar has visibly different facial/lighting treatment for happy, sad, strict/displeased, thinking, and sleeping.
2. During speech, the two hand overlays alternate and the chest/ear lights respond to audio amplitude without exceeding a gentle motion range.
3. Sleep cancels speech gestures and dims all lights.
4. The transparent avatar remains free of an opaque square on a real connected device.
5. Unit tests and the debug build pass.
