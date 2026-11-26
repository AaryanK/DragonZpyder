package xyz.dragonzpyder.benchmark

import android.content.ComponentName
import android.content.Intent
import androidx.benchmark.macro.CompilationMode
import androidx.benchmark.macro.FrameTimingMetric
import androidx.benchmark.macro.StartupMode
import androidx.benchmark.macro.StartupTimingMetric
import androidx.benchmark.macro.junit4.MacrobenchmarkRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class ReleaseBenchmarks {
    @get:Rule val benchmark=MacrobenchmarkRule()
    private val target="xyz.dragonzpyder.android.benchmark"

    // Measures first rendered frame, not network readiness or successful sign-in.
    @Test fun coldStartInitialDisplay()=benchmark.measureRepeated(
        packageName=target,metrics=listOf(StartupTimingMetric()),
        compilationMode=CompilationMode.None(),startupMode=StartupMode.COLD,iterations=20,
        setupBlock={pressHome()}
    ){startActivityAndWait()}

    // Local synthetic chat fixture is present only in the benchmark build type.
    @Test fun syntheticChatScroll()=benchmark.measureRepeated(
        packageName=target,metrics=listOf(FrameTimingMetric()),
        compilationMode=CompilationMode.None(),iterations=10,
        setupBlock={
            pressHome()
            startActivityAndWait(Intent().setComponent(ComponentName(target,
                "xyz.dragonzpyder.android.BenchmarkChatActivity")))
            device.waitForIdle()
        }
    ){
        val x=device.displayWidth/2
        val top=device.displayHeight*25/100
        val bottom=device.displayHeight*65/100
        repeat(5){
            check(device.swipe(x,top,x,bottom,20))
            check(device.swipe(x,bottom,x,top,20))
        }
        device.waitForIdle()
    }
}
