package xyz.dragonzpyder.android

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.width
import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.unit.dp
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class MarkdownRendererTest {
    @get:Rule val compose=createComposeRule()

    @Test fun screenshotTableRendersAsTwoColumnsWithoutLiteralPipes(){
        val markdown = "| Component | What it does |\n"+
            "|-----------|--------------|\n"+
            "| **Core agent** | Reasons and calls tools (`read_file`, `grep`, `glob`) |\n"+
            "| Persistent workflow engine (Operly) | Durable audited runs |"
        compose.setContent {
            MaterialTheme {
                Box(Modifier.width(350.dp)) { MarkdownBody(markdown,true,{}) }
            }
        }
        compose.onNodeWithText("Component").assertExists()
        compose.onNodeWithText("What it does").assertExists()
        compose.onNodeWithText("Core agent").assertExists()
        compose.onNodeWithText("Persistent workflow engine",substring=true).assertExists()
        compose.onNodeWithText("|-----------|",substring=true).assertDoesNotExist()
    }

    @Test fun mixedParagraphAndCodeBlocksRemainNativeAndCopyCorrectly(){
        val code="val result = foo()\nprintln(result)"
        var copied=""
        compose.setContent {
            MaterialTheme { Box(Modifier.width(340.dp)) {
                MarkdownBody("**Important** and `inline`\n\n```kotlin\n$code\n```\n\n> Note",false,{copied=it})
            } }
        }
        compose.onNodeWithText("Important",substring=true).assertExists()
        compose.onNodeWithText("val result",substring=true).assertExists()
        compose.onNodeWithText("Copy code").performClick()
        compose.runOnIdle { assertEquals(code+"\n",copied) }
        compose.onNodeWithText("Note",substring=true).assertExists()
    }
}
