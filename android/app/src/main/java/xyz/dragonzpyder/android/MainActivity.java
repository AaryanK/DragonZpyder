package xyz.dragonzpyder.android;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ComponentName;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import androidx.browser.customtabs.CustomTabsClient;
import androidx.browser.customtabs.CustomTabsIntent;
import androidx.browser.customtabs.CustomTabsServiceConnection;
import androidx.browser.customtabs.CustomTabsSession;
import androidx.browser.trusted.TrustedWebActivityIntentBuilder;

public final class MainActivity extends Activity {
    private static final Uri HOME = Uri.parse("https://dragonzpyder.xyz/app");
    private final Handler handler = new Handler(Looper.getMainLooper());
    private boolean launched, bound;
    private CustomTabsServiceConnection connection;
    private String browser;
    private final Runnable fallback = () -> launch(null);

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        browser = CustomTabsClient.getPackageName(this, null);
        if (browser == null) { launch(null); return; }
        connection = new CustomTabsServiceConnection() {
            @Override public void onCustomTabsServiceConnected(ComponentName name, CustomTabsClient client) {
                client.warmup(0);
                launch(client.newSession(null));
            }
            @Override public void onServiceDisconnected(ComponentName name) {}
        };
        handler.postDelayed(fallback, 1800);
        try {
            bound = CustomTabsClient.bindCustomTabsService(this, browser, connection);
        } catch (RuntimeException exception) {
            bound = false;
        }
        if (!bound) launch(null);
    }

    private void launch(CustomTabsSession session) {
        if (launched || isFinishing() || isDestroyed()) return;
        launched = true;
        handler.removeCallbacks(fallback);
        if (session != null) {
            try {
                new TrustedWebActivityIntentBuilder(HOME).build(session).launchTrustedWebActivity(this);
                finish();
                return;
            } catch (RuntimeException exception) {
                // Browser does not support TWA; use a standard browser tab.
            }
        }
        try {
            CustomTabsIntent tab = new CustomTabsIntent.Builder().setShowTitle(true).build();
            if (browser != null) tab.intent.setPackage(browser);
            tab.launchUrl(this, HOME);
            finish();
        } catch (RuntimeException exception) {
            try {
                startActivity(new Intent(Intent.ACTION_VIEW, HOME));
                finish();
            } catch (RuntimeException unavailable) {
                new AlertDialog.Builder(this).setMessage("Install or enable a web browser to open DragonZpyder.")
                    .setPositiveButton("Close", (dialog, which) -> finish()).setOnCancelListener(dialog -> finish()).show();
            }
        }
    }

    @Override protected void onDestroy() {
        handler.removeCallbacks(fallback);
        if (bound) unbindService(connection);
        super.onDestroy();
    }
}
