package com.example.digitalhuman.ui

import com.example.digitalhuman.network.ConnectionState
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class CompanionMotionTest {
    @Test fun listeningLeansInWithoutTalking() {
        val motion = companionMotion(ConnectionState.LISTENING, 0f)
        assertTrue(motion.tiltDegrees < 0f)
        assertEquals(0f, motion.talkLevel, 0.001f)
    }

    @Test fun thinkingTiltsOppositeToListening() {
        val motion = companionMotion(ConnectionState.THINKING, 0f)
        assertTrue(motion.tiltDegrees > 0f)
        assertEquals(0f, motion.talkLevel, 0.001f)
    }

    @Test fun speakingTracksBoundedAudioAmplitude() {
        val quiet = companionMotion(ConnectionState.SPEAKING, 0.1f)
        val loud = companionMotion(ConnectionState.SPEAKING, 2f)
        assertTrue(loud.talkLevel > quiet.talkLevel)
        assertEquals(1f, loud.talkLevel, 0.001f)
        assertTrue(loud.scale > quiet.scale)
    }

    @Test fun sleepingIsStillAndDimmer() {
        val motion = companionMotion(ConnectionState.SLEEPING, 0.8f)
        assertEquals(0f, motion.talkLevel, 0.001f)
        assertTrue(motion.opacity < 1f)
    }

    @Test fun invalidAudioLevelsNeverReachTheAnimation() {
        assertEquals(0f, companionMotion(ConnectionState.SPEAKING, Float.NaN).talkLevel, 0.001f)
        assertEquals(0f, companionMotion(ConnectionState.SPEAKING, -2f).talkLevel, 0.001f)
    }
}
