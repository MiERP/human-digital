package com.example.digitalhuman.ui

import org.junit.Assert.assertEquals
import org.junit.Test

class CompanionNameChoiceTest {
    @Test fun changingPresetUpdatesNameUnlessChildCustomizedIt() {
        assertEquals("Miu", nameAfterCompanionChoice("Siro", false, "Miu"))
        assertEquals("Bông", nameAfterCompanionChoice("Bông", true, "Miu"))
    }
}
