package com.example.digitalhuman.network

import org.junit.Assert.assertEquals
import org.junit.Test

class CompanionSelectionTest {
    private val preset = CompanionInfo(id = "girl_pink", name = "Miu", gender = "female", voice = "Aoede")

    @Test fun childChosenNameOverridesPreset() {
        val selected = resolveCompanion(preset, "  Bông  ", "female", "Aoede")
        assertEquals("Bông", selected.name)
        assertEquals("girl_pink", selected.id)
    }

    @Test fun blankChosenNameFallsBackToSelectedPreset() {
        val selected = resolveCompanion(preset, "   ", null, null)
        assertEquals("Miu", selected.name)
    }

    @Test fun legacyNullTextIsNotShownAsAName() {
        val selected = resolveCompanion(preset, "null", null, null)
        assertEquals("Miu", selected.name)
    }

    @Test fun serverDefaultCannotOverwriteChildsChosenName() {
        val ready = CompanionInfo(id = "girl_pink", name = "Dora")
        assertEquals("Bông", mergeCompanionName(preset.copy(name = "Bông"), ready).name)
    }

    @Test fun legacyUnconfiguredProfileDoesNotBecomeDoraOnConnect() {
        val ready = CompanionInfo(name = "Dora")
        assertEquals("Bạn Robot", mergeCompanionName(CompanionInfo(name = "Bạn Robot"), ready).name)
    }
}
