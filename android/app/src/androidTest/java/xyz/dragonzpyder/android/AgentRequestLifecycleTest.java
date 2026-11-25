package xyz.dragonzpyder.android;

import androidx.lifecycle.ViewModelProvider;
import androidx.activity.ComponentActivity;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public final class AgentRequestLifecycleTest {
    @Test public void recreationRetainsOneRequestAndNeverAutomaticallyReplays() throws Exception {
        AtomicReference<AgentRequestViewModel> original=new AtomicReference<>();
        AtomicInteger executions=new AtomicInteger();
        CountDownLatch entered=new CountDownLatch(1), release=new CountDownLatch(1);
        try(ActivityScenario<ComponentActivity> scenario=ActivityScenario.launch(ComponentActivity.class)){
            scenario.onActivity(activity->{
                AgentRequestViewModel vm=new ViewModelProvider(activity).get(AgentRequestViewModel.class);
                original.set(vm);
                vm.start("synthetic-id",()->{executions.incrementAndGet();entered.countDown();
                    if(!release.await(10,TimeUnit.SECONDS))throw new IllegalStateException("Fixture timeout");
                    return new JSONObject().put("message","test result");
                });
                assertTrue(vm.current().running);
            });
            assertTrue(entered.await(5,TimeUnit.SECONDS));
            scenario.recreate();
            scenario.onActivity(activity->{
                AgentRequestViewModel retained=new ViewModelProvider(activity).get(AgentRequestViewModel.class);
                assertSame(original.get(),retained);
                assertTrue(retained.current().running);
                assertEquals("synthetic-id",retained.current().id);
            });
            release.countDown();
            long until=System.nanoTime()+TimeUnit.SECONDS.toNanos(5);
            AtomicReference<AgentRequestViewModel.Outcome> result=new AtomicReference<>();
            do{
                scenario.onActivity(activity->result.set(original.get().current()));
                if(result.get()!=null&&!result.get().running)break;
                Thread.sleep(50);
            }while(System.nanoTime()<until);
            assertNotNull(result.get());assertFalse(result.get().running);
            assertEquals("test result",result.get().response.optString("message"));
            assertEquals(1,executions.get());
        }finally{release.countDown();}
    }
}
