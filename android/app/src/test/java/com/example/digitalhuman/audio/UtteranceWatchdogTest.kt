package com.example.digitalhuman.audio

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class UtteranceWatchdogTest {
    @Test fun normalTurnStaysOpen() {
        assertFalse(shouldForceEndUtterance(0))
        assertFalse(shouldForceEndUtterance(100))
        assertFalse(shouldForceEndUtterance(MAX_UTTERANCE_FRAMES - 1))
    }

    @Test fun continuousVadSpeechIsClosedAfterTheLimit() {
        assertTrue(shouldForceEndUtterance(MAX_UTTERANCE_FRAMES))
        assertTrue(shouldForceEndUtterance(MAX_UTTERANCE_FRAMES + 1))
    }
}
