package com.example.digitalhuman.audio

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SpeechOnsetFloorTest {
    @Test fun silentFrameCannotOpenATurn() {
        assertFalse(0.000f > speechOnsetFloor(playing = false, echoThreshold = 0.06f, noiseFloor = 0.004f))
    }

    @Test fun quietSpeechStillOpensATurn() {
        assertTrue(0.02f > speechOnsetFloor(playing = false, echoThreshold = 0.06f, noiseFloor = 0.004f))
    }

    @Test fun bargeInKeepsTheEchoThreshold() {
        assertEquals(0.06f, speechOnsetFloor(playing = true, echoThreshold = 0.06f, noiseFloor = 0.09f), 0.0001f)
    }

    @Test fun adaptiveFloorFollowsRoomNoise() {
        assertTrue(
            speechOnsetFloor(playing = false, echoThreshold = 0.06f, noiseFloor = 0.05f) >
                speechOnsetFloor(playing = false, echoThreshold = 0.06f, noiseFloor = 0.005f)
        )
    }
}
