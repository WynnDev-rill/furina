-keepattributes *Annotation*
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}

-keep class com.wynndev.furina.OfflineModelEngine { *; }
-keep class com.wynndev.furina.OfflineModelEngine$NativeListener { *; }
-keep class com.wynndev.furina.OfflineAiBridge { *; }
