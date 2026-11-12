package com.example.digitalhuman.ui

import com.example.digitalhuman.network.ConnectionState
import com.example.digitalhuman.network.RobotEmotion
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class CompanionMotionTest {
    @Test fun emotionSelectsDistinctFaceAndLightTreatments() {
        assertEquals(AvatarExpression.HAPPY, companionVisualState(ConnectionState.SPEAKING, RobotEmotion(emotion = "happy"), 0.5f, 0f).expression)
        assertEquals(AvatarExpression.SAD, companionVisualState(ConnectionState.LISTENING, RobotEmotion(emotion = "sad"), 0f, 0f).expression)
        assertEquals(AvatarExpression.STRICT, companionVisualState(ConnectionState.SPEAKING, RobotEmotion(emotion = "strict"), 0.5f, 0f).expression)
        assertEquals(AvatarExpression.THINKING, companionVisualState(ConnectionState.THINKING, RobotEmotion(), 0f, 0f).expression)
        assertEquals(AvatarExpression.SLEEPY, companionVisualState(ConnectionState.SLEEPING, RobotEmotion(emotion = "happy"), 1f, 0f).expression)
        assertEquals(AvatarExpression.SLEEPY, companionVisualState(ConnectionState.LISTENING, RobotEmotion(energy = "drowsy"), 0f, 0f).expression)
    }

    @Test fun tiredEnergyKeepsEyesOpenDuringConversation() {
        val tired = RobotEmotion(energy = "tired")
        assertEquals(AvatarExpression.NEUTRAL, companionVisualState(ConnectionState.LISTENING, tired, 0f, 0f).expression)
        assertEquals(AvatarExpression.NEUTRAL, companionVisualState(ConnectionState.SPEAKING, tired, 0.2f, 0f).expression)
        assertEquals(AvatarExpression.NEUTRAL, companionVisualState(ConnectionState.SPEAKING, RobotEmotion(energy = "sleepy"), 0.2f, 0f).expression)
        assertEquals(AvatarExpression.SLEEPY, companionVisualState(ConnectionState.SLEEPING, tired, 0f, 0f).expression)
    }

    @Test fun speakingAlternatesArmsAndLightsFollowSafeAudioLevel() {
        val first = companionVisualState(ConnectionState.SPEAKING, RobotEmotion(), 0.2f, 0f)
        val second = companionVisualState(ConnectionState.SPEAKING, RobotEmotion(), 0.2f, 1f)
        val louder = companionVisualState(ConnectionState.SPEAKING, RobotEmotion(), 1f, 0f)
        assertTrue(first.leftArmDegrees < second.leftArmDegrees)
        assertTrue(first.rightArmDegrees < second.rightArmDegrees)
        assertTrue(second.leftArmDegrees - first.leftArmDegrees > 3f)
        assertTrue(louder.lightEnergy > first.lightEnergy)
        assertTrue(louder.mouthOpen > first.mouthOpen)
        assertTrue(first.leftArmDegrees in -12f..12f)
        assertTrue(first.rightArmDegrees in -12f..12f)
    }

    @Test fun sleepDisablesSpeechMotionAndUnknownMoodIsNeutral() {
        val asleep = companionVisualState(ConnectionState.SLEEPING, RobotEmotion(), 1f, 1f)
        val unknown = companionVisualState(ConnectionState.LISTENING, RobotEmotion(emotion = "unexpected"), Float.NaN, 0f)
        assertEquals(0f, asleep.leftArmDegrees, 0.001f)
        assertEquals(0f, asleep.rightArmDegrees, 0.001f)
        assertEquals(0f, asleep.mouthOpen, 0.001f)
        assertTrue(asleep.lightEnergy < 0.3f)
        assertEquals(AvatarExpression.NEUTRAL, unknown.expression)
        assertTrue(unknown.lightEnergy.isFinite())
    }

    @Test fun avatarBobsAtRestAndPausesWhileSleeping() {
        assertTrue(companionBobOffset(ConnectionState.LISTENING, 0f, 0f) < 0f)
        assertTrue(companionBobOffset(ConnectionState.LISTENING, 0f, 1f) > 0f)
        assertEquals(0f, companionBobOffset(ConnectionState.SLEEPING, 1f, 0.5f), 0.001f)
    }

    @Test fun speakingBobRespondsMoreStronglyToLouderAudio() {
        val quiet = companionBobOffset(ConnectionState.SPEAKING, 0f, 0f)
        val loud = companionBobOffset(ConnectionState.SPEAKING, 1f, 0f)
        assertTrue(loud < quiet)
    }

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
        assertTrue(beatEnd.leftArmDegrees > beatStart.leftArmDegrees)
        assertTrue(beatEnd.rightArmDegrees > beatStart.rightArmDegrees)
        assertTrue(beatEnd.leftArmDegrees <= 4f)
        assertTrue(beatStart.rightArmDegrees >= -4f)
    }

    @Test fun quietSpeechUsesSmallerGesturesAndListeningDoesNotPulse() {
        val quiet = companionMotion(ConnectionState.SPEAKING, 0f, 1f)
        val loud = companionMotion(ConnectionState.SPEAKING, 1f, 1f)
        assertTrue(loud.leftArmDegrees > quiet.leftArmDegrees + 1f)
        assertEquals(
            companionMotion(ConnectionState.LISTENING, 0f, 0f).leftArmDegrees,
            companionMotion(ConnectionState.LISTENING, 0f, 1f).leftArmDegrees,
            0.001f,
        )
    }

    @Test fun ordinarySpeechLevelKeepsShoulderLiftGentle() {
        val motion = companionMotion(ConnectionState.SPEAKING, 0.08f, 1f)
        assertTrue(motion.leftArmDegrees in 2f..4f)
    }

    @Test fun speakingBendsElbowsAsHandsAlternate() {
        val start = companionMotion(ConnectionState.SPEAKING, 0.5f, 0f)
        val end = companionMotion(ConnectionState.SPEAKING, 0.5f, 1f)
        assertTrue(start.leftElbowDegrees in -20f..-15f)
        assertTrue(end.leftElbowDegrees in -28f..-23f)
        assertTrue(start.leftElbowDegrees - end.leftElbowDegrees in 5f..10f)
        assertTrue(end.rightElbowDegrees in 15f..20f)
        assertTrue(start.rightElbowDegrees - end.rightElbowDegrees in 5f..10f)
    }

    @Test fun idleElbowsStayRelaxedAndDoNotFollowSpeechBeat() {
        val listening = companionMotion(ConnectionState.LISTENING, 0.5f, 1f)
        assertEquals(0f, listening.leftElbowDegrees, 0.001f)
        assertEquals(0f, listening.rightElbowDegrees, 0.001f)
    }

    @Test fun elbowPulseFollowsVoiceLevelAndSettlesDuringSilence() {
        val silentStart = companionMotion(ConnectionState.SPEAKING, 0f, 0f)
        val silentEnd = companionMotion(ConnectionState.SPEAKING, 0f, 1f)
        val voicedEnd = companionMotion(ConnectionState.SPEAKING, 1f, 1f)
        assertEquals(-18f, silentStart.leftElbowDegrees, 0.001f)
        assertEquals(silentStart.leftElbowDegrees, silentEnd.leftElbowDegrees, 0.001f)
        assertTrue(voicedEnd.leftElbowDegrees < silentEnd.leftElbowDegrees - 5f)
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
