package com.example.digitalhuman.ui

import com.example.digitalhuman.network.ConnectionState
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class CompanionMotionTest {
    @Test fun listeningMovesEyesAndArmsWithoutTalking() {
        val motion = companionMotion(ConnectionState.LISTENING, 0f)
        assertTrue(motion.gazeX < 0f)
        assertTrue(motion.leftArmDegrees > 0f)
        assertTrue(motion.rightArmDegrees < 0f)
        assertEquals(0f, motion.talkLevel, 0.001f)
    }

    @Test fun thinkingLooksUpAndRaisesOneArm() {
        val motion = companionMotion(ConnectionState.THINKING, 0f)
        assertTrue(motion.gazeY < 0f)
        assertTrue(motion.rightArmDegrees < 0f)
        assertEquals(0f, motion.talkLevel, 0.001f)
    }

    @Test fun speakingTracksBoundedAudioAmplitude() {
        val quiet = companionMotion(ConnectionState.SPEAKING, 0.1f)
        val loud = companionMotion(ConnectionState.SPEAKING, 2f)
        assertTrue(loud.talkLevel > quiet.talkLevel)
        assertEquals(1f, loud.talkLevel, 0.001f)
        assertTrue(loud.leftArmDegrees > quiet.leftArmDegrees)
        assertTrue(loud.rightArmDegrees < quiet.rightArmDegrees)
    }

    @Test fun speakingArmsRiseAndFallAlternatelyAcrossGestureBeat() {
        val beatStart = companionMotion(ConnectionState.SPEAKING, 1f, 0f)
        val beatEnd = companionMotion(ConnectionState.SPEAKING, 1f, 1f)
        assertTrue(beatEnd.leftArmDegrees - beatStart.leftArmDegrees > 50f)
        assertTrue(beatEnd.rightArmDegrees - beatStart.rightArmDegrees > 50f)
        assertTrue(beatEnd.leftArmDegrees > 105f)
        assertTrue(beatStart.rightArmDegrees < -105f)
    }

    @Test fun quietSpeechUsesSmallerGesturesAndListeningDoesNotPulse() {
        val quiet = companionMotion(ConnectionState.SPEAKING, 0f, 1f)
        val loud = companionMotion(ConnectionState.SPEAKING, 1f, 1f)
        assertTrue(loud.leftArmDegrees > quiet.leftArmDegrees + 40f)
        assertEquals(
            companionMotion(ConnectionState.LISTENING, 0f, 0f).leftArmDegrees,
            companionMotion(ConnectionState.LISTENING, 0f, 1f).leftArmDegrees,
            0.001f,
        )
    }

    @Test fun ordinarySpeechLevelCanRaiseAHandAboveTheShoulder() {
        val motion = companionMotion(ConnectionState.SPEAKING, 0.08f, 1f)
        assertTrue(motion.leftArmDegrees > 105f)
    }

    @Test fun sleepingIsStillAndDimmer() {
        val motion = companionMotion(ConnectionState.SLEEPING, 0.8f)
        assertEquals(0f, motion.talkLevel, 0.001f)
        assertEquals(0f, motion.eyeOpen, 0.001f)
        assertTrue(motion.opacity < 1f)
    }

    @Test fun invalidAudioLevelsNeverReachTheAnimation() {
        assertEquals(0f, companionMotion(ConnectionState.SPEAKING, Float.NaN).talkLevel, 0.001f)
        assertEquals(0f, companionMotion(ConnectionState.SPEAKING, -2f).talkLevel, 0.001f)
    }
}
