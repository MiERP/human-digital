package com.example.digitalhuman.audio

import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AudioSessionLifecycleTest {
    @Test
    fun stopDuringInitializationCannotLeaveMicrophoneRunning() = runBlocking {
        val lifecycle = AudioSessionLifecycle()
        val token = lifecycle.begin()
        val entered = CountDownLatch(1)
        val release = CountDownLatch(1)
        var microphoneRunning = false

        val start = async(Dispatchers.IO) {
            lifecycle.start(token, onStart = {
                entered.countDown()
                assertTrue(release.await(3, TimeUnit.SECONDS))
                microphoneRunning = true
            }, onStop = { microphoneRunning = false })
        }
        assertTrue(entered.await(3, TimeUnit.SECONDS))
        val stopToken = lifecycle.end()
        release.countDown()
        lifecycle.stop(stopToken) { microphoneRunning = false }
        start.await()

        assertFalse(microphoneRunning)
    }

    @Test
    fun staleStopDoesNotCloseNewSession() = runBlocking {
        val lifecycle = AudioSessionLifecycle()
        val first = lifecycle.begin()
        val staleStop = lifecycle.end()
        val second = lifecycle.begin()
        var running = false

        lifecycle.start(second, onStart = { running = true }, onStop = { running = false })
        lifecycle.stop(staleStop) { running = false }

        assertTrue(running)
        assertTrue(second > first)
    }
}
