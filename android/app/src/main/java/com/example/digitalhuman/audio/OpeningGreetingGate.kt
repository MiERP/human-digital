package com.example.digitalhuman.audio

/** Chặn mic cho đến khi lời chào mở đầu thực sự phát xong. */
class OpeningGreetingGate {
    private var sessionActive = false
    private var waitingForGreeting = false
    private var greetingPlaybackStarted = false

    @get:Synchronized
    val allowMic: Boolean
        get() = sessionActive && !waitingForGreeting

    @Synchronized
    fun startSession() {
        sessionActive = true
        waitingForGreeting = true
        greetingPlaybackStarted = false
    }

    @Synchronized
    fun onPlaybackStarted() {
        if (waitingForGreeting) greetingPlaybackStarted = true
    }

    @Synchronized
    fun onPlaybackFinished() {
        if (waitingForGreeting && greetingPlaybackStarted) {
            waitingForGreeting = false
        }
    }

    @Synchronized
    fun onTurnCompleteWithoutAudio() {
        if (waitingForGreeting && !greetingPlaybackStarted) {
            waitingForGreeting = false
        }
    }

    @Synchronized
    fun stopSession() {
        sessionActive = false
        waitingForGreeting = false
        greetingPlaybackStarted = false
    }
}
