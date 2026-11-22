package xyz.dragonzpyder.android;

import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import java.util.HashSet;
import java.util.Set;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public final class ProviderSignInUiTest {
    private void collect(View view,Set<String> labels){
        if(view instanceof TextView)labels.add(((TextView)view).getText().toString());
        if(view.getContentDescription()!=null)labels.add(view.getContentDescription().toString());
        if(view instanceof ViewGroup){
            ViewGroup parent=(ViewGroup)view;
            for(int i=0;i<parent.getChildCount();i++)collect(parent.getChildAt(i),labels);
        }
    }
    @Test public void providerChoicesPresentInSignInAndSignup(){
        try(ActivityScenario<MainActivity> scenario=ActivityScenario.launch(MainActivity.class)){
            scenario.onActivity(activity->{
                try{
                    java.lang.reflect.Method m=MainActivity.class.getDeclaredMethod("authScreen",String.class,String.class);
                    m.setAccessible(true);
                    for(String mode:new String[]{"login","signup"}){
                        m.invoke(activity,mode,"");
                        Set<String> labels=new HashSet<>();
                        collect(activity.getWindow().getDecorView(),labels);
                        assertTrue(labels.toString(),labels.stream().anyMatch(x->x.contains("Continue with Google")));
                        assertTrue(labels.toString(),labels.stream().anyMatch(x->x.contains("Continue with Discord")));
                    }
                }catch(ReflectiveOperationException e){throw new AssertionError(e);}
            });
        }
    }
}
