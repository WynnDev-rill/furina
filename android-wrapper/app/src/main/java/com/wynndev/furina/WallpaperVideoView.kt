package com.wynndev.furina

import android.content.Context
import android.graphics.Matrix
import android.graphics.SurfaceTexture
import android.media.MediaPlayer
import android.view.Surface
import android.view.TextureView

/** Texture composition respects Compose clipping/dimming; no SurfaceView overlay or audio focus. */
internal class WallpaperVideoView(context: Context) : TextureView(context), TextureView.SurfaceTextureListener {
    private var player: MediaPlayer? = null
    private var surface: Surface? = null
    private var path = ""
    private var allowed = false
    private var prepared = false
    private var position = 1
    private var failed = false
    var onFailure: () -> Unit = {}

    init { surfaceTextureListener = this; isOpaque = false; isClickable = false; importantForAccessibility = IMPORTANT_FOR_ACCESSIBILITY_NO }

    fun configure(nextPath: String, motion: Boolean, foreground: Boolean) {
        allowed = motion && foreground
        if (path != nextPath) { releasePlayer(); path = nextPath; failed = false; position = 1 }
        if (player == null && isAvailable && !failed) open()
        updatePlayback()
    }

    private fun open() {
        val texture = surfaceTexture ?: return
        if (path.isBlank() || failed || player != null) return
        try {
            val output = Surface(texture); surface = output
            val media = MediaPlayer(); player = media
            media.setSurface(output); media.setVolume(0f, 0f); media.isLooping = true
            media.setOnPreparedListener {
                if (player === it) {
                    prepared = true; crop(it.videoWidth, it.videoHeight)
                    it.seekTo(position); updatePlayback()
                }
            }
            media.setOnVideoSizeChangedListener { _, width, height -> crop(width, height) }
            media.setOnErrorListener { _, _, _ -> failed = true; releasePlayer(); onFailure(); true }
            media.setDataSource(path); media.prepareAsync()
        } catch (_: Exception) { failed = true; releasePlayer(); onFailure() }
    }

    private fun updatePlayback() {
        val media = player ?: return
        if (!prepared) return
        try { if (allowed) { if (!media.isPlaying) media.start() } else if (media.isPlaying) media.pause() }
        catch (_: IllegalStateException) { failed = true; releasePlayer(); onFailure() }
    }

    private fun crop(videoWidth: Int, videoHeight: Int) {
        if (width <= 0 || height <= 0 || videoWidth <= 0 || videoHeight <= 0) return
        val scale = maxOf(width.toFloat() / videoWidth, height.toFloat() / videoHeight)
        setTransform(Matrix().apply { setScale(scale * videoWidth / width, scale * videoHeight / height, width / 2f, height / 2f) })
    }

    fun releasePlayer() {
        player?.let { if (prepared) position = runCatching { it.currentPosition }.getOrDefault(1); it.setOnPreparedListener(null); it.setOnErrorListener(null); it.setOnVideoSizeChangedListener(null); it.release() }
        player = null; prepared = false; surface?.release(); surface = null
    }
    override fun onSurfaceTextureAvailable(texture: SurfaceTexture, width: Int, height: Int) { open() }
    override fun onSurfaceTextureSizeChanged(texture: SurfaceTexture, width: Int, height: Int) { player?.let { if (prepared) crop(it.videoWidth, it.videoHeight) } }
    override fun onSurfaceTextureDestroyed(texture: SurfaceTexture): Boolean { releasePlayer(); return true }
    override fun onSurfaceTextureUpdated(texture: SurfaceTexture) = Unit
    override fun onDetachedFromWindow() { releasePlayer(); super.onDetachedFromWindow() }
}
