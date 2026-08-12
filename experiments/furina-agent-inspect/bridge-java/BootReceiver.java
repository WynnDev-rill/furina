package com.wynndev.furinaagentbridge;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

public class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        if (BridgePrefs.isPersistentEnabled(context)) {
            BridgeForegroundService.start(context);
        }
    }
}
