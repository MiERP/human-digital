package com.example.digitalhuman.audio

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class InterruptionGateTest {
    @Test
    fun serverAcknowledgementDoesNotFlushTwiceAfterLocalBargeIn() {
        val gate = InterruptionGate()
        gate.onLocalInterruption()

        assertFalse(gate.shouldFlushOnServerInterruption())
        assertTrue(gate.shouldFlushOnServerInterruption())
    }

    @Test
    fun serverOnlyInterruptionStillFlushes() {
        assertTrue(InterruptionGate().shouldFlushOnServerInterruption())
    }

    @Test
    fun newSessionDiscardsOldPendingAcknowledgement() {
        val gate = InterruptionGate()
        gate.onLocalInterruption()
        gate.reset()
        assertTrue(gate.shouldFlushOnServerInterruption())
    }
}
