package xyz.dragonzpyder.android

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import org.junit.Assert.*
import org.junit.Test

class DesignContractTest {
    private fun contrast(a:Color,b:Color):Float{
        val x=a.luminance()
        val y=b.luminance()
        return (maxOf(x,y)+.05f)/(minOf(x,y)+.05f)
    }
    @Test fun coreTextAndPrimaryActionsMeetAaContrast(){
        for(dark in listOf(false,true)){
            val t=DragonDesignTokens.of(dark)
            for(background in listOf(t.background,t.surface,t.bubble)){
                assertTrue("body contrast",contrast(t.ink,background)>=4.5f)
                assertTrue("secondary contrast",contrast(t.muted,background)>=4.5f)
            }
            assertTrue("primary contrast",contrast(t.onAccent,t.accent)>=4.5f)
            assertTrue("control contrast",contrast(t.outline,t.surface)>=3f)
        }
    }
    @Test fun executionConsentStartsOffEvenWhenCapabilitiesBecomeAvailable(){
        val state=ChatPresentationState()
        state.update{it.copy(computerAvailable=true,mediaAvailable=true,durableAvailable=true)}
        assertFalse(state.snapshot.allowComputer)
        assertFalse(state.snapshot.allowMedia)
        assertFalse(state.snapshot.allowDurable)
        assertTrue(state.snapshot.computerAvailable)
    }
    @Test fun sizingContract(){
        assertTrue(DragonSizes.touch.value>=48)
        assertTrue(DragonSizes.icon.value>=24)
    }
    @Test fun immutableStatePreservesUnchangedFields(){
        val state=ChatPresentationState()
        state.update{it.copy(draft="Preserve draft",filesAvailable=true)}
        val previous=state.snapshot
        state.update{it.copy(busy=true,streaming=true)}
        assertEquals("Preserve draft",state.snapshot.draft)
        assertTrue(state.snapshot.filesAvailable)
        assertTrue(state.snapshot.streaming)
        assertFalse(previous.busy)
        assertFalse(previous.streaming)
    }
    @Test fun filenamesRejectPathTraversalAndControlCharacters(){
        for(name in listOf("../x","a/b","a\\b","\u202Eevil.exe","\u0000x","..",".")){
            assertFalse(name,AgentFileRepository.safeFilename(name))
        }
        assertTrue(AgentFileRepository.safeFilename("Research report.pdf"))
        assertTrue(AgentFileRepository.safeFilename("分析.xlsx"))
    }
}
