package xyz.dragonzpyder.android;

import android.text.InputType;
import android.text.method.PasswordTransformationMethod;
import android.view.inputmethod.EditorInfo;
import android.widget.EditText;

/** Apply only after configuring line count and any generic input settings. */
final class SecurePasswordField {
    static final int TYPE=InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD;
    private SecurePasswordField(){}
    static void configure(EditText field) {
        field.setSingleLine(true);
        field.setInputType(TYPE);
        field.setTransformationMethod(PasswordTransformationMethod.getInstance());
        field.setImeOptions(EditorInfo.IME_FLAG_NO_PERSONALIZED_LEARNING | EditorInfo.IME_FLAG_NO_EXTRACT_UI);
        field.setSaveEnabled(false);
        field.setFreezesText(false);
    }
}
