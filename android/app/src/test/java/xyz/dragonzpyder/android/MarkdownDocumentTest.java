package xyz.dragonzpyder.android;

import org.commonmark.ext.gfm.tables.TableBlock;
import org.commonmark.node.*;
import org.junit.Test;
import java.util.*;
import static org.junit.Assert.*;

public final class MarkdownDocumentTest {
    private static boolean contains(Node n,Class<?> kind){
        if(kind.isInstance(n))return true;
        for(Node c=n.getFirstChild();c!=null;c=c.getNext())if(contains(c,kind))return true;
        return false;
    }
    @Test public void realScreenshotTableHasStructuredCells(){
        String source="DragonZpyder is the agent platform.\n\n"+
            "| Component | What it does |\n"+
            "|-----------|--------------|\n"+
            "| **Core agent** | Reasons and calls tools (`read_file`, grep) |\n"+
            "| Persistent workflow engine | Durable work |";
        Node doc=MarkdownDocument.parse(source);
        assertTrue("GFM pipes must become a TableBlock",contains(doc,TableBlock.class));
        assertTrue(contains(doc,Code.class));
        assertTrue(contains(doc,StrongEmphasis.class));
        assertTrue(MarkdownDocument.plain(doc).contains("Core agent"));
        assertFalse(MarkdownDocument.plain(doc).contains("|-----------|"));
    }
    @Test public void complexBlocksAreSemanticNotSplitLines(){
        String source="# Heading\n\n> Quoted **text**\n\n1. Ordered item\n2. Second item\n\n"+
            "- Bullet\n  - Nested item\n\n```kotlin\nval x = \"safe\"\n```\n\n~~deleted~~";
        Node doc=MarkdownDocument.parse(source);
        assertTrue(contains(doc,Heading.class));
        assertTrue(contains(doc,BlockQuote.class));
        assertTrue(contains(doc,OrderedList.class));
        assertTrue(contains(doc,BulletList.class));
        assertTrue(contains(doc,FencedCodeBlock.class));
    }
    @Test public void maliciousHtmlIsParsedButNeverExecuted(){
        Node doc=MarkdownDocument.parse("<script>alert('x')</script>\n\n[bad](javascript:alert(1))");
        assertTrue(contains(doc,HtmlBlock.class));
        assertTrue(MarkdownDocument.plain(doc).contains("<script>"));
        assertNotNull(doc);
    }
    @Test public void boundedLongReply(){
        String source="A".repeat(MarkdownDocument.MAX_CHARS+120);
        Node doc=MarkdownDocument.parse(source);
        assertTrue(MarkdownDocument.plain(doc).contains("[Long reply truncated"));
        assertTrue(MarkdownDocument.plain(doc).length()<MarkdownDocument.MAX_CHARS+120);
    }
}
