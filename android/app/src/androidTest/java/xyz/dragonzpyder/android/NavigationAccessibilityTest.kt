package xyz.dragonzpyder.android

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.width
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class NavigationAccessibilityTest {
    @get:Rule val compose=createComposeRule()

    @Test fun compactNavigationRemainsReachableAtTwoHundredPercentText(){
        var taps=0
        compose.setContent {
            val density=LocalDensity.current
            CompositionLocalProvider(LocalDensity provides Density(density.density,2f)){
                DragonTheme(false){
                    Box(Modifier.width(280.dp)){
                        Column {
                            DragonNavigationRow("Connections & tools","connections",false,selected=true){taps++}
                            DragonNavigationRow("Account","account",false,enabled=false){taps++}
                        }
                    }
                }
            }
        }
        compose.onNodeWithText("Connections & tools").assertIsDisplayed()
            .assertIsSelected().assertHasClickAction()
            .assertHeightIsAtLeast(48.dp).assertWidthIsAtLeast(48.dp).performClick()
        compose.onNodeWithText("Account").assertIsDisplayed().assertIsNotEnabled()
            .assertHeightIsAtLeast(48.dp).assertWidthIsAtLeast(48.dp)
        compose.runOnIdle{assertEquals(1,taps)}
    }

    @Test fun contextualMenuSearchAndDismissHaveAccessibleActions(){
        var chosen=""
        var dismissed=false
        compose.setContent {
            NativeCommandPalette(listOf(
                CommandItem("Switch mode","more",Runnable{chosen="mode"}),
                CommandItem("Dictate a message","mic",Runnable{chosen="dictate"})
            ),true){dismissed=true}
        }
        compose.onNodeWithContentDescription("Close commands").assertIsDisplayed()
            .assertHasClickAction().assertHeightIsAtLeast(48.dp)
        compose.onNodeWithText("Search actions").performTextInput("Dictate")
        compose.onNodeWithText("Switch mode").assertDoesNotExist()
        compose.onNodeWithText("Dictate a message").assertIsDisplayed()
            .assertHeightIsAtLeast(48.dp).performClick()
        compose.runOnIdle{assertEquals("dictate",chosen);assertEquals(true,dismissed)}
    }
}
