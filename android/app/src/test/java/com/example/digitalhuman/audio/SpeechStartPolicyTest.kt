package com.example.digitalhuman.audio

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SpeechStartPolicyTest {
    @Test fun briefReplyJustAfterPlaybackNeedsAtMostTwoSpeechFrames() {
        assertTrue(requiredSpeechOnsetFrames(playing = false) <= 2)
    }

    @Test fun activePlaybackRetainsStrongerEchoProtection() {
        assertTrue(requiredSpeechOnsetFrames(playing = true) > requiredSpeechOnsetFrames(playing = false))
    }

    @Test fun ordinaryListeningKeepsFastSpeechStart() {
        assertEquals(2, requiredSpeechOnsetFrames(playing = false))
    }
}
