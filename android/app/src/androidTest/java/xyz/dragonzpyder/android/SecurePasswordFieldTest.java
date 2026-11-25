package xyz.dragonzpyder.android;

import android.text.InputType;
import android.text.method.PasswordTransformationMethod;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.EditText;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import org.junit.Test;
import org.junit.runner.RunWith;
import java.util.ArrayList;
import static org.junit.Assert.*;

/** Runtime tests use dummy text only; never submit real credentials. */
@RunWith(AndroidJUnit4.class)
public final class SecurePasswordFieldTest {
    private void collect(View root, ArrayList<EditText> fields){
        if(root instanceof EditText){
            EditText field=(EditText)root;
            String[] hints=field.getAutofillHints();
            if(hints!=null)for(String hint:hints)if(hint.equals("password")||hint.equals("newPassword"))fields.add(field);
        }
        if(root instanceof ViewGroup){ViewGroup group=(ViewGroup)root;for(int i=0;i<group.getChildCount();i++)collect(group.getChildAt(i),fields);}
    }
    private void verify(EditText field){
        String dummy="Dummy-Secret-123";
        field.setText(dummy);
        assertEquals(InputType.TYPE_TEXT_VARIATION_PASSWORD,field.getInputType() & InputType.TYPE_MASK_VARIATION);
        assertTrue(field.getTransformationMethod() instanceof PasswordTransformationMethod);
        CharSequence displayed=field.getTransformationMethod().getTransformation(field.getText(),field);
        assertFalse(dummy.contentEquals(displayed));
        assertFalse(field.isSaveEnabled());
        field.setText("");
    }
    @Test public void loginPasswordMasked(){
        try(ActivityScenario<MainActivity> scenario=ActivityScenario.launch(MainActivity.class)){
            scenario.onActivity(app->verifyScreen(app,1));
        }
    }
    @Test public void signupAndResetPasswordMasked(){
        try(ActivityScenario<MainActivity> scenario=ActivityScenario.launch(MainActivity.class)){
            scenario.onActivity(app->{
                try{
                    java.lang.reflect.Method method=MainActivity.class.getDeclaredMethod("authScreen",String.class,String.class);
                    method.setAccessible(true);
                    method.invoke(app,"signup","");
                    verifyScreen(app,2);
                    method.invoke(app,"reset","");
                    verifyScreen(app,1);
                }catch(ReflectiveOperationException e){throw new AssertionError(e);}
            });
        }
    }
    private void verifyScreen(MainActivity app,int count){
        ArrayList<EditText> fields=new ArrayList<>();
        collect(app.getWindow().getDecorView(),fields);
        assertEquals(count,fields.size());
        for(EditText field:fields)verify(field);
        // Screenshot support is intentional; masking and disabled password state saving still apply.
        assertEquals(0,app.getWindow().getAttributes().flags & WindowManager.LayoutParams.FLAG_SECURE);
    }
    @Test public void genericSingleLineCannotOverrideMask(){
        try(ActivityScenario<MainActivity> scenario=ActivityScenario.launch(MainActivity.class)){
            scenario.onActivity(app->{
                EditText field=new EditText(app);
                field.setInputType(SecurePasswordField.TYPE);
                field.setSingleLine(true);
                SecurePasswordField.configure(field);
                verify(field);
            });
        }
    }
}
