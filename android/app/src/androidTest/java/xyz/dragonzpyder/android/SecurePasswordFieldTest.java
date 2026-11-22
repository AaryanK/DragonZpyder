package xyz.dragonzpyder.android;

import android.app.Instrumentation;
import android.test.ActivityInstrumentationTestCase2;
import android.text.InputType;
import android.text.method.PasswordTransformationMethod;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.EditText;
import android.widget.Button;
import java.util.ArrayList;

/** Uses dummy data only; does not submit a real account or password. */
@SuppressWarnings("deprecation")
public final class SecurePasswordFieldTest extends ActivityInstrumentationTestCase2<MainActivity> {
    public SecurePasswordFieldTest(){super(MainActivity.class);}
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
    public void testLoginPasswordMasked() throws Throwable {
        MainActivity app=getActivity();
        runTestOnUiThread(()->{
            ArrayList<EditText> fields=new ArrayList<>();
            collect(app.getWindow().getDecorView(),fields);
            assertEquals(1,fields.size());
            verify(fields.get(0));
            assertTrue((app.getWindow().getAttributes().flags & WindowManager.LayoutParams.FLAG_SECURE)!=0);
        });
    }
    public void testGenericSingleLineCannotOverrideMask() throws Throwable {
        MainActivity app=getActivity();
        runTestOnUiThread(()->{
            EditText field=new EditText(app);
            field.setInputType(SecurePasswordField.TYPE);
            field.setSingleLine(true);
            SecurePasswordField.configure(field);
            verify(field);
        });
    }
}
