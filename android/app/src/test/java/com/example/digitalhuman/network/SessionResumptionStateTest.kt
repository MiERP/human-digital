package com.example.digitalhuman.network

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class SessionResumptionStateTest {
    @Test
    fun reconnectUsesLatestHandleButNewSessionDoesNot() {
        val state = SessionResumptionState()
        assertNull(state.handleForReconnect())

        state.acceptUpdate("first-handle", "first-key")
        state.acceptUpdate("newer-handle", "second-key")
        assertEquals("newer-handle", state.handleForReconnect())
        assertEquals("second-key", state.keyIdForReconnect())

        state.beginNewSession()
        assertNull(state.handleForReconnect())
        assertNull(state.keyIdForReconnect())
    }

    @Test
    fun nonResumableUpdateClearsOldHandle() {
        val state = SessionResumptionState()
        state.acceptUpdate("valid-handle", "key-id")
        state.acceptUpdate("", "")
        assertNull(state.handleForReconnect())
        assertNull(state.keyIdForReconnect())
    }
}
