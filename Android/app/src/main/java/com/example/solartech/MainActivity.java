package com.example.solartech;

import android.content.Context;
import android.content.SharedPreferences;
import android.net.wifi.WifiManager;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.view.View;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.EditText;
import android.widget.ImageButton;
import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;

public class MainActivity extends AppCompatActivity {

    private boolean pageHasError = false;
    private View splashContainer;
    private WebView webView;
    private SharedPreferences prefs;
    private static final String PREF_IP = "server_ip";
    private static final String DEFAULT_IP = "192.168.1.112";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
        );

        setContentView(R.layout.activity_main);

        prefs = getSharedPreferences("SolarTechPrefs", MODE_PRIVATE);

        // First time launch check: auto-detect connected Wi-Fi gateway IP if possible
        if (!prefs.contains(PREF_IP)) {
            String detectedIp = getConnectedWifiGatewayIp();
            if (detectedIp != null && !detectedIp.isEmpty() && !detectedIp.equals("0.0.0.0")) {
                prefs.edit().putString(PREF_IP, detectedIp).apply();
            } else {
                prefs.edit().putString(PREF_IP, DEFAULT_IP).apply();
            }
        }

        splashContainer = findViewById(R.id.splashContainer);
        webView = findViewById(R.id.webView);
        ImageButton btnSettings = findViewById(R.id.btnSettings);

        if (btnSettings != null) {
            btnSettings.setOnClickListener(v -> showIpDialog());
        }

        // Essential WebView settings
        webView.getSettings().setJavaScriptEnabled(true);
        webView.getSettings().setUseWideViewPort(true);
        webView.getSettings().setLoadWithOverviewMode(true);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                super.onReceivedError(view, request, error);
                if (request.isForMainFrame()) {
                    pageHasError = true;
                }
            }

            @Deprecated
            @Override
            public void onReceivedError(WebView view, int errorCode, String description, String failingUrl) {
                super.onReceivedError(view, errorCode, description, failingUrl);
                pageHasError = true;
            }
        });

        loadAppWithCurrentIp();
    }

    private String getConnectedWifiGatewayIp() {
        try {
            WifiManager wifiManager = (WifiManager) getApplicationContext().getSystemService(Context.WIFI_SERVICE);
            if (wifiManager != null) {
                int gatewayInt = wifiManager.getDhcpInfo().gateway;
                if (gatewayInt != 0) {
                    return android.text.format.Formatter.formatIpAddress(gatewayInt);
                }
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
        return null;
    }

    private void loadAppWithCurrentIp() {
        pageHasError = false;
        if (splashContainer != null) {
            splashContainer.setVisibility(View.VISIBLE);
        }
        if (webView != null) {
            webView.setVisibility(View.GONE);
        }

        String ip = prefs.getString(PREF_IP, DEFAULT_IP);
        String url = "http://" + ip + ":3000/deviceDetail.html";

        webView.loadUrl(url);

        // Check after 2.5 seconds: if webpage loaded successfully, transition to WebView.
        // If webpage is not available (error occurred), stay on splash screen.
        new Handler(Looper.getMainLooper()).postDelayed(() -> {
            if (!pageHasError) {
                if (splashContainer != null) {
                    splashContainer.setVisibility(View.GONE);
                }
                if (webView != null) {
                    webView.setVisibility(View.VISIBLE);
                }
            }
        }, 2500);
    }

    private void showIpDialog() {
        AlertDialog.Builder builder = new AlertDialog.Builder(this);
        builder.setTitle("Enter Device IP Address");

        final EditText input = new EditText(this);
        input.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        input.setText(prefs.getString(PREF_IP, DEFAULT_IP));
        input.setSelection(input.getText().length());
        builder.setView(input);

        builder.setPositiveButton("Save & Reload", (dialog, which) -> {
            String newIp = input.getText().toString().trim();
            if (!newIp.isEmpty()) {
                prefs.edit().putString(PREF_IP, newIp).apply();
                loadAppWithCurrentIp();
            }
        });
        builder.setNegativeButton("Cancel", (dialog, which) -> dialog.cancel());

        builder.show();
    }
}
