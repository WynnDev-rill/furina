package com.wynndev.furinaagentbridge;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.ImageDecoder;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.PointF;
import android.graphics.RectF;
import android.os.Bundle;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowInsets;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Native editor used instead of the WebView image/canvas pipeline.
 *
 * The source bitmap, crop rectangle, annotations and exported pixels all live
 * in the same Android Canvas coordinate system. This deliberately removes the
 * CSS layer ordering and WebView GPU decode path that produced black previews
 * on some HyperOS/WebView combinations.
 */
public final class NativeImageEditorActivity extends Activity {
    public static final String EXTRA_SOURCE = "source_path";
    public static final String EXTRA_OUTPUT = "output_path";
    public static final String EXTRA_NAME = "output_name";
    public static final String EXTRA_MIME = "output_mime";

    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private EditorView editor;
    private Button cropButton;
    private Button drawButton;
    private Button undoButton;
    private Button doneButton;
    private TextView status;
    private String sourcePath;
    private String outputPath;
    private String outputName;
    private String sourceMime;

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        sourcePath = String.valueOf(getIntent().getStringExtra(EXTRA_SOURCE));
        outputPath = String.valueOf(getIntent().getStringExtra(EXTRA_OUTPUT));
        outputName = String.valueOf(getIntent().getStringExtra(EXTRA_NAME));
        sourceMime = String.valueOf(getIntent().getStringExtra(EXTRA_MIME));
        if (!new File(sourcePath).isFile() || !new File(outputPath).getParentFile().isDirectory()) {
            finishWithError("File gambar tidak tersedia.");
            return;
        }
        getWindow().setStatusBarColor(Color.rgb(18, 17, 23));
        getWindow().setNavigationBarColor(Color.rgb(18, 17, 23));
        setContentView(buildUi());
        loadBitmap();
    }

    private View buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.BLACK);

        LinearLayout bar = new LinearLayout(this);
        bar.setGravity(Gravity.CENTER_VERTICAL);
        bar.setPadding(dp(8), 0, dp(8), 0);
        bar.setBackgroundColor(Color.rgb(18, 17, 23));

        Button close = tool("✕");
        close.setContentDescription("Batal");
        close.setOnClickListener(v -> {
            setResult(RESULT_CANCELED);
            finish();
        });
        bar.addView(close, new LinearLayout.LayoutParams(dp(52), dp(56)));

        status = new TextView(this);
        status.setText("Membuka gambar…");
        status.setTextColor(Color.WHITE);
        status.setTextSize(14);
        status.setGravity(Gravity.CENTER_VERTICAL);
        bar.addView(status, new LinearLayout.LayoutParams(0, dp(56), 1f));

        cropButton = tool("Pangkas");
        cropButton.setOnClickListener(v -> setMode(EditorView.MODE_CROP));
        bar.addView(cropButton, new LinearLayout.LayoutParams(dp(82), dp(56)));

        drawButton = tool("Coret");
        drawButton.setOnClickListener(v -> setMode(EditorView.MODE_DRAW));
        bar.addView(drawButton, new LinearLayout.LayoutParams(dp(68), dp(56)));

        undoButton = tool("↶");
        undoButton.setContentDescription("Urungkan coretan");
        undoButton.setOnClickListener(v -> editor.undo());
        bar.addView(undoButton, new LinearLayout.LayoutParams(dp(48), dp(56)));

        doneButton = tool("Selesai");
        doneButton.setTextColor(Color.rgb(141, 124, 255));
        doneButton.setOnClickListener(v -> saveResult());
        bar.addView(doneButton, new LinearLayout.LayoutParams(dp(78), dp(56)));
        root.addView(bar, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(56)));

        editor = new EditorView();
        root.addView(editor, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        root.setOnApplyWindowInsetsListener((view, insets) -> {
            int top = 0, bottom = 0;
            if (android.os.Build.VERSION.SDK_INT >= 30) {
                top = insets.getInsets(WindowInsets.Type.statusBars()).top;
                bottom = insets.getInsets(WindowInsets.Type.navigationBars()).bottom;
            }
            bar.setPadding(dp(8), top, dp(8), 0);
            ViewGroup.LayoutParams p = bar.getLayoutParams();
            p.height = dp(56) + top;
            bar.setLayoutParams(p);
            editor.setPadding(0, 0, 0, bottom);
            return insets;
        });
        setControls(false);
        return root;
    }

    private Button tool(String text) {
        Button button = new Button(this);
        button.setText(text);
        button.setTextSize(13);
        button.setTextColor(Color.WHITE);
        button.setAllCaps(false);
        button.setGravity(Gravity.CENTER);
        button.setPadding(dp(2), 0, dp(2), 0);
        button.setBackgroundColor(Color.TRANSPARENT);
        return button;
    }

    private void setControls(boolean enabled) {
        cropButton.setEnabled(enabled);
        drawButton.setEnabled(enabled);
        undoButton.setEnabled(enabled);
        doneButton.setEnabled(enabled);
        float alpha = enabled ? 1f : 0.4f;
        cropButton.setAlpha(alpha);
        drawButton.setAlpha(alpha);
        undoButton.setAlpha(alpha);
        doneButton.setAlpha(alpha);
    }

    private void setMode(int mode) {
        editor.setMode(mode);
        cropButton.setAlpha(mode == EditorView.MODE_CROP ? 1f : 0.58f);
        drawButton.setAlpha(mode == EditorView.MODE_DRAW ? 1f : 0.58f);
        status.setText(mode == EditorView.MODE_CROP ? "Geser tepi untuk memangkas" : "Coret langsung pada gambar");
    }

    private void loadBitmap() {
        io.execute(() -> {
            try {
                ImageDecoder.Source source = ImageDecoder.createSource(new File(sourcePath));
                Bitmap bitmap = ImageDecoder.decodeBitmap(source, (decoder, info, ignored) -> {
                    int width = info.getSize().getWidth();
                    int height = info.getSize().getHeight();
                    int longest = Math.max(width, height);
                    if (longest > 4096) {
                        float scale = 4096f / longest;
                        decoder.setTargetSize(
                                Math.max(1, Math.round(width * scale)),
                                Math.max(1, Math.round(height * scale)));
                    }
                    decoder.setAllocator(ImageDecoder.ALLOCATOR_SOFTWARE);
                    decoder.setMutableRequired(false);
                });
                runOnUiThread(() -> {
                    editor.setBitmap(bitmap);
                    setControls(true);
                    setMode(EditorView.MODE_CROP);
                });
            } catch (Throwable error) {
                runOnUiThread(() -> finishWithError("Gambar gagal didekode: " + error.getMessage()));
            }
        });
    }

    private void saveResult() {
        if (!editor.ready()) return;
        setControls(false);
        status.setText("Menyimpan hasil…");
        io.execute(() -> {
            try {
                Bitmap output = editor.renderResult();
                boolean preserveAlpha = "image/png".equals(sourceMime) || "image/webp".equals(sourceMime);
                String mime = preserveAlpha ? "image/png" : "image/jpeg";
                Bitmap.CompressFormat format = preserveAlpha ? Bitmap.CompressFormat.PNG : Bitmap.CompressFormat.JPEG;
                ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                output.compress(format, preserveAlpha ? 100 : 94, bytes);
                if (bytes.size() > 5_800_000) {
                    bytes.reset();
                    Bitmap flattened = Bitmap.createBitmap(output.getWidth(), output.getHeight(), Bitmap.Config.ARGB_8888);
                    Canvas canvas = new Canvas(flattened);
                    canvas.drawColor(Color.WHITE);
                    canvas.drawBitmap(output, 0, 0, null);
                    flattened.compress(Bitmap.CompressFormat.JPEG, 86, bytes);
                    flattened.recycle();
                    mime = "image/jpeg";
                }
                output.recycle();
                if (bytes.size() <= 0 || bytes.size() > 6_000_000) {
                    throw new IllegalStateException("Hasil gambar melebihi batas 6 MB.");
                }
                try (FileOutputStream out = new FileOutputStream(outputPath)) {
                    bytes.writeTo(out);
                    out.getFD().sync();
                }
                String ext = "image/png".equals(mime) ? ".png" : ".jpg";
                String base = outputName == null ? "gambar" : outputName.replaceFirst("\\.[^.]+$", "");
                Intent result = new Intent()
                        .putExtra(EXTRA_OUTPUT, outputPath)
                        .putExtra(EXTRA_NAME, base + "-edit" + ext)
                        .putExtra(EXTRA_MIME, mime);
                runOnUiThread(() -> {
                    setResult(RESULT_OK, result);
                    finish();
                });
            } catch (Throwable error) {
                runOnUiThread(() -> {
                    setControls(true);
                    status.setText("Gagal menyimpan");
                    Toast.makeText(this, String.valueOf(error.getMessage()), Toast.LENGTH_LONG).show();
                });
            }
        });
    }

    private void finishWithError(String message) {
        Toast.makeText(this, message, Toast.LENGTH_LONG).show();
        setResult(RESULT_CANCELED);
        finish();
    }

    @Override
    protected void onDestroy() {
        io.shutdownNow();
        super.onDestroy();
    }

    private final class EditorView extends View {
        static final int MODE_CROP = 1;
        static final int MODE_DRAW = 2;
        private static final int DRAG_NONE = 0;
        private static final int DRAG_MOVE = 1;
        private static final int DRAG_LEFT = 2;
        private static final int DRAG_TOP = 4;
        private static final int DRAG_RIGHT = 8;
        private static final int DRAG_BOTTOM = 16;

        private final Paint imagePaint = new Paint(Paint.ANTI_ALIAS_FLAG | Paint.FILTER_BITMAP_FLAG);
        private final Paint overlayPaint = new Paint();
        private final Paint cropPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint pathPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final RectF imageRect = new RectF();
        private final RectF cropRect = new RectF();
        private final List<Stroke> strokes = new ArrayList<>();
        private Bitmap bitmap;
        private Stroke activeStroke;
        private int mode = MODE_CROP;
        private int drag = DRAG_NONE;
        private float lastX;
        private float lastY;

        EditorView() {
            super(NativeImageEditorActivity.this);
            setBackgroundColor(Color.BLACK);
            overlayPaint.setColor(0x99000000);
            cropPaint.setColor(Color.WHITE);
            cropPaint.setStyle(Paint.Style.STROKE);
            cropPaint.setStrokeWidth(dp(2));
            pathPaint.setStyle(Paint.Style.STROKE);
            pathPaint.setStrokeCap(Paint.Cap.ROUND);
            pathPaint.setStrokeJoin(Paint.Join.ROUND);
            setLayerType(View.LAYER_TYPE_HARDWARE, null);
        }

        void setBitmap(Bitmap value) {
            bitmap = value;
            layoutBitmap();
            invalidate();
        }

        void setMode(int value) {
            mode = value;
            activeStroke = null;
            invalidate();
        }

        boolean ready() {
            return bitmap != null && !bitmap.isRecycled() && cropRect.width() >= 2 && cropRect.height() >= 2;
        }

        void undo() {
            if (!strokes.isEmpty()) strokes.remove(strokes.size() - 1);
            activeStroke = null;
            invalidate();
        }

        @Override
        protected void onSizeChanged(int w, int h, int oldw, int oldh) {
            layoutBitmap();
        }

        private void layoutBitmap() {
            if (bitmap == null || getWidth() <= 0 || getHeight() <= 0) return;
            float availableW = getWidth() - getPaddingLeft() - getPaddingRight();
            float availableH = getHeight() - getPaddingTop() - getPaddingBottom();
            float scale = Math.min(availableW / bitmap.getWidth(), availableH / bitmap.getHeight());
            float width = bitmap.getWidth() * scale;
            float height = bitmap.getHeight() * scale;
            float left = getPaddingLeft() + (availableW - width) / 2f;
            float top = getPaddingTop() + (availableH - height) / 2f;
            imageRect.set(left, top, left + width, top + height);
            cropRect.set(imageRect);
        }

        @Override
        protected void onDraw(Canvas canvas) {
            super.onDraw(canvas);
            if (!ready()) return;
            canvas.drawBitmap(bitmap, null, imageRect, imagePaint);
            for (Stroke stroke : strokes) drawStroke(canvas, stroke);
            if (activeStroke != null) drawStroke(canvas, activeStroke);
            if (mode == MODE_CROP) drawCrop(canvas);
        }

        private void drawStroke(Canvas canvas, Stroke stroke) {
            if (stroke.points.isEmpty()) return;
            pathPaint.setColor(stroke.color);
            pathPaint.setStrokeWidth(stroke.width);
            Path path = new Path();
            PointF first = stroke.points.get(0);
            path.moveTo(first.x, first.y);
            for (int i = 1; i < stroke.points.size(); i++) {
                PointF point = stroke.points.get(i);
                path.lineTo(point.x, point.y);
            }
            canvas.save();
            canvas.clipRect(imageRect);
            canvas.drawPath(path, pathPaint);
            canvas.restore();
        }

        private void drawCrop(Canvas canvas) {
            canvas.drawRect(imageRect.left, imageRect.top, imageRect.right, cropRect.top, overlayPaint);
            canvas.drawRect(imageRect.left, cropRect.bottom, imageRect.right, imageRect.bottom, overlayPaint);
            canvas.drawRect(imageRect.left, cropRect.top, cropRect.left, cropRect.bottom, overlayPaint);
            canvas.drawRect(cropRect.right, cropRect.top, imageRect.right, cropRect.bottom, overlayPaint);
            canvas.drawRect(cropRect, cropPaint);
            Paint grid = new Paint(cropPaint);
            grid.setColor(0x88FFFFFF);
            grid.setStrokeWidth(dp(1));
            for (int i = 1; i <= 2; i++) {
                float x = cropRect.left + cropRect.width() * i / 3f;
                float y = cropRect.top + cropRect.height() * i / 3f;
                canvas.drawLine(x, cropRect.top, x, cropRect.bottom, grid);
                canvas.drawLine(cropRect.left, y, cropRect.right, y, grid);
            }
            Paint handle = new Paint(Paint.ANTI_ALIAS_FLAG);
            handle.setColor(Color.WHITE);
            float radius = dp(5);
            canvas.drawCircle(cropRect.left, cropRect.top, radius, handle);
            canvas.drawCircle(cropRect.right, cropRect.top, radius, handle);
            canvas.drawCircle(cropRect.left, cropRect.bottom, radius, handle);
            canvas.drawCircle(cropRect.right, cropRect.bottom, radius, handle);
        }

        @Override
        public boolean onTouchEvent(MotionEvent event) {
            if (!ready()) return false;
            float x = clamp(event.getX(), imageRect.left, imageRect.right);
            float y = clamp(event.getY(), imageRect.top, imageRect.bottom);
            if (mode == MODE_DRAW) return drawTouch(event, x, y);
            return cropTouch(event, x, y);
        }

        private boolean drawTouch(MotionEvent event, float x, float y) {
            if (event.getActionMasked() == MotionEvent.ACTION_DOWN) {
                activeStroke = new Stroke(Color.rgb(141, 124, 255), Math.max(dp(3), imageRect.width() * 0.012f));
                activeStroke.points.add(new PointF(x, y));
                invalidate();
                return true;
            }
            if (activeStroke == null) return false;
            if (event.getActionMasked() == MotionEvent.ACTION_MOVE) {
                activeStroke.points.add(new PointF(x, y));
                invalidate();
                return true;
            }
            if (event.getActionMasked() == MotionEvent.ACTION_UP) {
                activeStroke.points.add(new PointF(x, y));
                if (activeStroke.points.size() > 1) strokes.add(activeStroke);
                activeStroke = null;
                invalidate();
                return true;
            }
            if (event.getActionMasked() == MotionEvent.ACTION_CANCEL) {
                activeStroke = null;
                invalidate();
                return true;
            }
            return true;
        }

        private boolean cropTouch(MotionEvent event, float x, float y) {
            if (event.getActionMasked() == MotionEvent.ACTION_DOWN) {
                drag = hitCrop(x, y);
                lastX = x;
                lastY = y;
                return true;
            }
            if (event.getActionMasked() == MotionEvent.ACTION_MOVE && drag != DRAG_NONE) {
                float dx = x - lastX;
                float dy = y - lastY;
                float min = dp(88);
                if (drag == DRAG_MOVE) {
                    cropRect.offset(dx, dy);
                    if (cropRect.left < imageRect.left) cropRect.offset(imageRect.left - cropRect.left, 0);
                    if (cropRect.right > imageRect.right) cropRect.offset(imageRect.right - cropRect.right, 0);
                    if (cropRect.top < imageRect.top) cropRect.offset(0, imageRect.top - cropRect.top);
                    if (cropRect.bottom > imageRect.bottom) cropRect.offset(0, imageRect.bottom - cropRect.bottom);
                } else {
                    if ((drag & DRAG_LEFT) != 0) cropRect.left = clamp(x, imageRect.left, cropRect.right - min);
                    if ((drag & DRAG_RIGHT) != 0) cropRect.right = clamp(x, cropRect.left + min, imageRect.right);
                    if ((drag & DRAG_TOP) != 0) cropRect.top = clamp(y, imageRect.top, cropRect.bottom - min);
                    if ((drag & DRAG_BOTTOM) != 0) cropRect.bottom = clamp(y, cropRect.top + min, imageRect.bottom);
                }
                lastX = x;
                lastY = y;
                invalidate();
                return true;
            }
            if (event.getActionMasked() == MotionEvent.ACTION_UP || event.getActionMasked() == MotionEvent.ACTION_CANCEL) {
                drag = DRAG_NONE;
                return true;
            }
            return true;
        }

        private int hitCrop(float x, float y) {
            float hit = dp(34);
            int value = DRAG_NONE;
            if (Math.abs(x - cropRect.left) <= hit) value |= DRAG_LEFT;
            else if (Math.abs(x - cropRect.right) <= hit) value |= DRAG_RIGHT;
            if (Math.abs(y - cropRect.top) <= hit) value |= DRAG_TOP;
            else if (Math.abs(y - cropRect.bottom) <= hit) value |= DRAG_BOTTOM;
            if (value != DRAG_NONE) return value;
            return cropRect.contains(x, y) ? DRAG_MOVE : DRAG_NONE;
        }

        Bitmap renderResult() {
            if (!ready()) throw new IllegalStateException("Editor belum siap.");
            float sx = bitmap.getWidth() / imageRect.width();
            float sy = bitmap.getHeight() / imageRect.height();
            int sourceX = Math.max(0, Math.round((cropRect.left - imageRect.left) * sx));
            int sourceY = Math.max(0, Math.round((cropRect.top - imageRect.top) * sy));
            int width = Math.min(bitmap.getWidth() - sourceX, Math.max(1, Math.round(cropRect.width() * sx)));
            int height = Math.min(bitmap.getHeight() - sourceY, Math.max(1, Math.round(cropRect.height() * sy)));
            Bitmap result = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888);
            Canvas canvas = new Canvas(result);
            if (!("image/png".equals(sourceMime) || "image/webp".equals(sourceMime))) canvas.drawColor(Color.WHITE);
            RectF destination = new RectF(0, 0, width, height);
            android.graphics.Rect source = new android.graphics.Rect(sourceX, sourceY, sourceX + width, sourceY + height);
            canvas.drawBitmap(bitmap, source, destination, imagePaint);
            Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
            paint.setStyle(Paint.Style.STROKE);
            paint.setStrokeCap(Paint.Cap.ROUND);
            paint.setStrokeJoin(Paint.Join.ROUND);
            for (Stroke stroke : strokes) {
                if (stroke.points.isEmpty()) continue;
                Path path = new Path();
                PointF first = stroke.points.get(0);
                path.moveTo((first.x - cropRect.left) * sx, (first.y - cropRect.top) * sy);
                for (int i = 1; i < stroke.points.size(); i++) {
                    PointF point = stroke.points.get(i);
                    path.lineTo((point.x - cropRect.left) * sx, (point.y - cropRect.top) * sy);
                }
                paint.setColor(stroke.color);
                paint.setStrokeWidth(stroke.width * Math.max(sx, sy));
                canvas.drawPath(path, paint);
            }
            return result;
        }

        private float clamp(float value, float low, float high) {
            return Math.max(low, Math.min(high, value));
        }
    }

    private static final class Stroke {
        final int color;
        final float width;
        final List<PointF> points = new ArrayList<>();

        Stroke(int color, float width) {
            this.color = color;
            this.width = width;
        }
    }
}
