package com.wynndev.furinaagentbridge;

import android.Manifest;
import android.app.Activity;
import android.content.ComponentName;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

public class MainActivity extends Activity {
    private final Handler handler = new Handler(Looper.getMainLooper());
    private TextView bridgeChip;
    private TextView accessibilityChip;
    private TextView diagnostic;
    private TextView linkStatus;
    private TextView updateStatus;
    private Button updateButton;
    private Button persistentButton;
    private BridgeUpdater bridgeUpdater;

    private final Runnable refresher = new Runnable() {
        @Override public void run() {
            refresh();
            handler.postDelayed(this, 1500);
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        BridgeForegroundService.start(this);
        requestNotificationsIfNeeded();
        setContentView(buildUi());
        bridgeUpdater = new BridgeUpdater(this, updateStatus, updateButton);
        bridgeUpdater.check(false);
    }

    @Override protected void onResume() {
        super.onResume();
        BridgePrefs.openBootstrapWindow(this, 120_000L);
        handler.removeCallbacks(refresher);
        handler.post(refresher);
        if (bridgeUpdater != null) bridgeUpdater.onResume();
    }

    @Override protected void onPause() {
        handler.removeCallbacks(refresher);
        super.onPause();
    }

    private View buildUi() {
        int pad = dp(20);
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(Color.rgb(7, 10, 18));

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(pad, dp(28), pad, dp(36));
        scroll.addView(root, new ScrollView.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        TextView eyebrow = text("LOCAL COMPANION BRIDGE  •  BY WYNN", 12, Color.rgb(125, 211, 252), Typeface.BOLD);
        root.addView(eyebrow, matchWrap());

        TextView title = text("Furina Bridge", 32, Color.WHITE, Typeface.BOLD);
        LinearLayout.LayoutParams titleP = matchWrap(); titleP.topMargin = dp(8); root.addView(title, titleP);

        TextView desc = text("Bridge lokal antara Furina Core di Termux dan Android. Server tetap hidup sebagai foreground service; Accessibility dapat tersambung kembali tanpa mematikan core.", 15, Color.rgb(166, 176, 201), Typeface.NORMAL);
        LinearLayout.LayoutParams descP = matchWrap(); descP.topMargin = dp(10); root.addView(desc, descP);

        LinearLayout chips = new LinearLayout(this);
        chips.setOrientation(LinearLayout.HORIZONTAL);
        chips.setGravity(Gravity.START);
        LinearLayout.LayoutParams chipsP = matchWrap(); chipsP.topMargin = dp(20); root.addView(chips, chipsP);
        bridgeChip = chip(); accessibilityChip = chip();
        chips.addView(bridgeChip);
        LinearLayout.LayoutParams acp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT); acp.leftMargin = dp(8);
        chips.addView(accessibilityChip, acp);

        LinearLayout statusCard = card();
        LinearLayout.LayoutParams cardP = matchWrap(); cardP.topMargin = dp(18); root.addView(statusCard, cardP);
        statusCard.addView(sectionTitle("STATUS"));
        diagnostic = text("Memeriksa…", 14, Color.rgb(210, 218, 235), Typeface.NORMAL);
        diagnostic.setTypeface(Typeface.MONOSPACE);
        LinearLayout.LayoutParams diagP = matchWrap(); diagP.topMargin = dp(12); statusCard.addView(diagnostic, diagP);

        LinearLayout updateCard = card();
        LinearLayout.LayoutParams updateP = matchWrap(); updateP.topMargin = dp(14); root.addView(updateCard, updateP);
        updateCard.addView(sectionTitle("UPDATE"));
        updateStatus = text("Memeriksa versi terbaru…", 14, Color.rgb(210, 218, 235), Typeface.NORMAL);
        LinearLayout.LayoutParams updateTextP = matchWrap(); updateTextP.topMargin = dp(10); updateCard.addView(updateStatus, updateTextP);
        updateButton = actionButton("Periksa update", false);
        updateButton.setOnClickListener(v -> {
            if (bridgeUpdater != null) bridgeUpdater.checkOrInstall();
        });
        updateCard.addView(updateButton, buttonParams(12));

        persistentButton = actionButton("Aktifkan persistent bridge", true);
        persistentButton.setOnClickListener(v -> {
            if (BridgePrefs.isPersistentEnabled(this)) BridgeForegroundService.stopPersistent(this);
            else BridgeForegroundService.start(this);
            refresh();
        });
        root.addView(persistentButton, buttonParams(18));

        Button access = actionButton("Buka Accessibility", false);
        access.setOnClickListener(v -> startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)));
        root.addView(access, buttonParams(10));

        Button battery = actionButton("Battery: No restrictions", false);
        battery.setOnClickListener(v -> openBatterySettings());
        root.addView(battery, buttonParams(10));

        Button autostart = actionButton("Buka Autostart HyperOS", false);
        autostart.setOnClickListener(v -> openXiaomiAutostart());
        root.addView(autostart, buttonParams(10));

        LinearLayout linkCard = card();
        LinearLayout.LayoutParams linkP = matchWrap(); linkP.topMargin = dp(22); root.addView(linkCard, linkP);
        linkCard.addView(sectionTitle("TERMUX LINK"));
        linkStatus = text("", 14, Color.rgb(226, 232, 240), Typeface.NORMAL);
        LinearLayout.LayoutParams linkTextP = matchWrap(); linkTextP.topMargin = dp(12); linkCard.addView(linkStatus, linkTextP);

        Button openWindow = actionButton("Hubungkan Termux otomatis", false);
        openWindow.setOnClickListener(v -> {
            BridgePrefs.openBootstrapWindow(this, 120_000L);
            Toast.makeText(this, "Auto-connect aktif selama 2 menit. Kembali ke Termux dan jalankan furina connect.", Toast.LENGTH_LONG).show();
            refresh();
        });
        linkCard.addView(openWindow, buttonParams(12));

        TextView note = text("Untuk HyperOS: set Furina Bridge dan Termux ke No restrictions, aktifkan Autostart, lalu lock keduanya di Recent Apps.", 13, Color.rgb(125, 140, 170), Typeface.NORMAL);
        LinearLayout.LayoutParams noteP = matchWrap(); noteP.topMargin = dp(20); root.addView(note, noteP);

        return scroll;
    }

    private void refresh() {
        if (bridgeChip == null) return;
        boolean persistent = BridgePrefs.isPersistentEnabled(this);
        boolean fg = BridgeRuntime.foregroundAlive();
        boolean acc = BridgeRuntime.accessibilityBound();
        setChip(bridgeChip, fg ? "● BRIDGE LIVE" : "○ BRIDGE OFF", fg);
        setChip(accessibilityChip, acc ? "● ACCESSIBILITY" : "○ ACCESSIBILITY", acc);
        persistentButton.setText(persistent ? "Matikan persistent bridge" : "Aktifkan persistent bridge");
        diagnostic.setText(
                "Loopback      127.0.0.1:8765\n" +
                "Foreground    " + (fg ? "RUNNING" : "STOPPED") + "\n" +
                "Accessibility " + (acc ? "BOUND" : "UNBOUND") + "\n" +
                "Mode          " + (persistent ? "PERSISTENT" : "MANUAL")
        );
        long lastClient = BridgeRuntime.lastAuthorizedClientAt();
        boolean linkedRecently = lastClient > 0 && (System.currentTimeMillis() - lastClient) < 10 * 60_000L;
        linkStatus.setText(
                (linkedRecently ? "● Termux terhubung" : "○ Menunggu Termux") +
                "\nTidak ada kode pairing. Buka layar ini lalu jalankan: furina connect" +
                (BridgePrefs.bootstrapOpen(this) ? "\nAuto-connect window: AKTIF" : "")
        );
    }

    private void requestNotificationsIfNeeded() {
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 22);
        }
    }

    private void openBatterySettings() {
        try {
            Intent app = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:" + getPackageName()));
            startActivity(app);
        } catch (Throwable t) {
            startActivity(new Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS));
        }
    }

    private void openXiaomiAutostart() {
        try {
            Intent i = new Intent();
            i.setComponent(new ComponentName("com.miui.securitycenter", "com.miui.permcenter.autostart.AutoStartManagementActivity"));
            startActivity(i);
        } catch (Throwable t) {
            Toast.makeText(this, "Menu Autostart khusus Xiaomi tidak ditemukan. Buka App info → Autostart secara manual.", Toast.LENGTH_LONG).show();
            openBatterySettings();
        }
    }

    private LinearLayout card() {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(18), dp(18), dp(18), dp(18));
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(Color.rgb(17, 23, 38));
        bg.setCornerRadius(dp(20));
        bg.setStroke(dp(1), Color.rgb(37, 48, 74));
        card.setBackground(bg);
        return card;
    }

    private TextView sectionTitle(String value) {
        return text(value, 12, Color.rgb(125, 211, 252), Typeface.BOLD);
    }

    private TextView chip() {
        TextView v = text("", 11, Color.WHITE, Typeface.BOLD);
        v.setPadding(dp(12), dp(7), dp(12), dp(7));
        return v;
    }

    private void setChip(TextView v, String label, boolean active) {
        v.setText(label);
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(active ? Color.rgb(17, 58, 72) : Color.rgb(42, 45, 57));
        bg.setCornerRadius(dp(99));
        bg.setStroke(dp(1), active ? Color.rgb(56, 189, 248) : Color.rgb(75, 85, 99));
        v.setBackground(bg);
        v.setTextColor(active ? Color.rgb(186, 230, 253) : Color.rgb(180, 186, 199));
    }

    private Button actionButton(String label, boolean primary) {
        Button b = new Button(this);
        b.setText(label);
        b.setAllCaps(false);
        b.setTextSize(15);
        b.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        b.setTextColor(primary ? Color.rgb(5, 16, 27) : Color.rgb(226, 232, 240));
        b.setPadding(dp(16), dp(12), dp(16), dp(12));
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(primary ? Color.rgb(125, 211, 252) : Color.rgb(24, 32, 51));
        bg.setCornerRadius(dp(16));
        if (!primary) bg.setStroke(dp(1), Color.rgb(50, 63, 91));
        b.setBackground(bg);
        return b;
    }

    private TextView text(String value, int sp, int color, int style) {
        TextView t = new TextView(this);
        t.setText(value);
        t.setTextSize(sp);
        t.setTextColor(color);
        t.setTypeface(Typeface.DEFAULT, style);
        t.setLineSpacing(0, 1.08f);
        return t;
    }

    private LinearLayout.LayoutParams matchWrap() {
        return new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
    }

    private LinearLayout.LayoutParams buttonParams(int top) {
        LinearLayout.LayoutParams p = matchWrap();
        p.topMargin = dp(top);
        return p;
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
