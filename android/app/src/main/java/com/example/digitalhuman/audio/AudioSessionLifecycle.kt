package com.example.digitalhuman.audio

import java.util.concurrent.atomic.AtomicInteger
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/** Tuần tự hóa khởi tạo/dừng audio mà không chặn luồng giao diện. */
internal class AudioSessionLifecycle {
    private val generation = AtomicInteger(0)
    private val mutex = Mutex()

    fun begin(): Int = generation.incrementAndGet()

    fun end(): Int = generation.incrementAndGet()

    suspend fun start(token: Int, onStart: () -> Unit, onStop: () -> Unit) {
        mutex.withLock {
            if (token != generation.get()) return@withLock
            // Dọn phiên trước nếu bé dừng rồi mở phiên mới rất nhanh.
            onStop()
            if (token != generation.get()) return@withLock
            var started = false
            try {
                onStart()
                started = true
            } finally {
                // end() có thể chạy trong lúc VAD/AudioTrack khởi tạo.
                if (!started || token != generation.get()) onStop()
            }
        }
    }

    suspend fun stop(token: Int, onStop: () -> Unit) {
        mutex.withLock {
            if (token == generation.get()) onStop()
        }
    }
}
