package xyz.dragonzpyder.android

import org.junit.Assert.*
import org.junit.Test

class MathMarkupTest {
    @Test fun extractsExplicitAndDollarMath(){
        val doc=MathMarkup.extract("Inline \\(x^2\\) and \u0024y\u0024.\n\\[\\frac{1}{2}\\]")
        assertEquals(3,doc.formulas.size)
        assertEquals("x^2",doc.formulas.values.first().latex)
        assertTrue(doc.formulas.values.last().display)
        assertFalse(doc.formulas.values.first().display)
    }
    @Test fun keepsCodeAndCurrency(){
        val tick=96.toChar().toString()
        val source=tick+"\u0024x\u0024"+tick+"\n"+tick.repeat(3)+"\n\\[a\\]\n"+tick.repeat(3)+"\nPrice \u00245.00"
        assertEquals(source,MathMarkup.extract(source).source)
        assertTrue(MathMarkup.extract(source).formulas.isEmpty())
    }
    @Test fun boundsAndReservedTokens(){
        assertTrue(MathMarkup.extract("DZMATHTOKEN0END \\(x\\)").formulas.isEmpty())
        assertTrue(MathMarkup.extract("\\("+"a".repeat(2049)+"\\)").formulas.isEmpty())
        assertEquals(64,MathMarkup.extract("\\(a\\) ".repeat(100)).formulas.size)
    }
}
