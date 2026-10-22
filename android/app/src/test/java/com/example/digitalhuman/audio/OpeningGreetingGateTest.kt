package com.example.digitalhuman.audio

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class OpeningGreetingGateTest {
    @Test fun openingMicWaitsForGreetingPlaybackToFinish() {
        val gate = OpeningGreetingGate()
        gate.startSession()
        assertFalse(gate.allowMic)

        // AudioPlayer cũng phát callback false khi khởi tạo hoặc chưa có audio.
        gate.onPlaybackFinished()
        assertFalse(gate.allowMic)

        gate.onPlaybackStarted()
        assertFalse(gate.allowMic)
        gate.onPlaybackFinished()
        assertTrue(gate.allowMic)
    }

    @Test fun anotherSessionNeedsItsOwnGreeting() {
        val gate = OpeningGreetingGate()
        gate.startSession()
        gate.onPlaybackStarted()
        gate.onPlaybackFinished()
        gate.stopSession()
        gate.startSession()
        assertFalse(gate.allowMic)
    }

    @Test fun laterPlaybackKeepsBargeInAvailable() {
        val gate = OpeningGreetingGate()
        gate.startSession()
        gate.onPlaybackStarted()
        gate.onPlaybackFinished()
        gate.onPlaybackStarted()
        assertTrue(gate.allowMic)
    }

    @Test fun greetingWithoutAudioDoesNotMuteMicForever() {
        val gate = OpeningGreetingGate()
        gate.startSession()
        gate.onTurnCompleteWithoutAudio()
        assertTrue(gate.allowMic)
    }
}
