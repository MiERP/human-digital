package com.example.digitalhuman.camera

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Matrix
import android.util.Log
import android.util.Size
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleOwner
import java.io.ByteArrayOutputStream
import java.util.concurrent.Executors

/**
 * Quản lý CameraX và trích xuất khung hình JPEG thời gian thực cho "Mắt Thần Doraemon":
 * - Độ phân giải tối ưu: ~512x512 px (tối ưu hóa độ trễ và băng thông mạng).
 * - Điều tiết tốc độ khung hình (Throttle): đúng 1 khung hình/giây (1 FPS) theo chuẩn Google Gemini Live API.
 * - Hỗ trợ lật camera Trước (Selfie) / Sau (Soi bài tập, đồ vật, tranh vẽ).
 * - Tự động nén JPEG chất lượng 65% (~25-35 KB/frame).
 */
class CameraStreamManager(
    private val context: Context,
    private val onFrameCaptured: (ByteArray) -> Unit
) {
    companion object {
        private const val TAG = "CameraStreamManager"
        private const val FRAME_INTERVAL_MS = 1000L // 1 FPS theo chuẩn Gemini Live API
        private const val TARGET_MAX_DIMENSION = 512
        private const val JPEG_QUALITY = 65
    }

    private val cameraExecutor = Executors.newSingleThreadExecutor()
    private var cameraProvider: ProcessCameraProvider? = null
    private var isStreaming = false
    private var lastFrameTimestamp = 0L
    private var isFrontCamera = false

    fun startCamera(
        lifecycleOwner: LifecycleOwner,
        previewView: PreviewView?,
        useFrontCamera: Boolean = false,
        onStarted: () -> Unit = {}
    ) {
        isFrontCamera = useFrontCamera
        isStreaming = true

        val cameraProviderFuture = ProcessCameraProvider.getInstance(context)
        cameraProviderFuture.addListener({
            try {
                cameraProvider = cameraProviderFuture.get()
                bindCamera(lifecycleOwner, previewView)
                onStarted()
            } catch (e: Exception) {
                Log.e(TAG, "Lỗi khởi động CameraX: ${e.message}", e)
            }
        }, ContextCompat.getMainExecutor(context))
    }

    fun switchCamera(lifecycleOwner: LifecycleOwner, previewView: PreviewView?) {
        isFrontCamera = !isFrontCamera
        bindCamera(lifecycleOwner, previewView)
    }

    private fun bindCamera(lifecycleOwner: LifecycleOwner, previewView: PreviewView?) {
        val provider = cameraProvider ?: return
        provider.unbindAll()

        val cameraSelector = if (isFrontCamera) {
            CameraSelector.DEFAULT_FRONT_CAMERA
        } else {
            CameraSelector.DEFAULT_BACK_CAMERA
        }

        // 1. Preview use case (cho giao diện người dùng xem)
        val preview = Preview.Builder()
            .build()
            .also {
                if (previewView != null) {
                    it.setSurfaceProvider(previewView.surfaceProvider)
                }
            }

        // 2. ImageAnalysis use case (để trích xuất frame gửi lên server)
        val imageAnalysis = ImageAnalysis.Builder()
            .setTargetResolution(Size(TARGET_MAX_DIMENSION, TARGET_MAX_DIMENSION))
            .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
            .build()

        imageAnalysis.setAnalyzer(cameraExecutor) { imageProxy ->
            processFrame(imageProxy)
        }

        try {
            provider.bindToLifecycle(
                lifecycleOwner,
                cameraSelector,
                preview,
                imageAnalysis
            )
            Log.d(TAG, "Camera đã liên kết thành công (Front=$isFrontCamera)")
        } catch (e: Exception) {
            Log.e(TAG, "Không thể liên kết CameraX với lifecycle: ${e.message}", e)
        }
    }

    private fun processFrame(imageProxy: ImageProxy) {
        if (!isStreaming) {
            imageProxy.close()
            return
        }

        val now = System.currentTimeMillis()
        if (now - lastFrameTimestamp < FRAME_INTERVAL_MS) {
            imageProxy.close()
            return
        }
        lastFrameTimestamp = now

        try {
            val bitmap = imageProxy.toBitmap()
            val rotationDegrees = imageProxy.imageInfo.rotationDegrees

            // Xoay ảnh theo đúng chiều hiển thị
            val rotatedBitmap = if (rotationDegrees != 0 || isFrontCamera) {
                val matrix = Matrix().apply {
                    postRotate(rotationDegrees.toFloat())
                    if (isFrontCamera) {
                        // Lật gương cho camera trước
                        postScale(-1f, 1f, bitmap.width / 2f, bitmap.height / 2f)
                    }
                }
                Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
            } else {
                bitmap
            }

            // Scale về kích thước tối ưu 512x512
            val scaledBitmap = scaleBitmapToMaxDimension(rotatedBitmap, TARGET_MAX_DIMENSION)

            val outputStream = ByteArrayOutputStream()
            scaledBitmap.compress(Bitmap.CompressFormat.JPEG, JPEG_QUALITY, outputStream)
            val jpegBytes = outputStream.toByteArray()

            if (scaledBitmap != bitmap && !scaledBitmap.isRecycled) {
                scaledBitmap.recycle()
            }
            if (rotatedBitmap != bitmap && !rotatedBitmap.isRecycled) {
                rotatedBitmap.recycle()
            }
            if (!bitmap.isRecycled) {
                bitmap.recycle()
            }

            onFrameCaptured(jpegBytes)
        } catch (e: Exception) {
            Log.e(TAG, "Lỗi khi xử lý frame camera: ${e.message}", e)
        } finally {
            imageProxy.close()
        }
    }

    private fun scaleBitmapToMaxDimension(source: Bitmap, maxDim: Int): Bitmap {
        val width = source.width
        val height = source.height
        if (width <= maxDim && height <= maxDim) return source

        val ratio = width.toFloat() / height.toFloat()
        val targetWidth: Int
        val targetHeight: Int
        if (width > height) {
            targetWidth = maxDim
            targetHeight = (maxDim / ratio).toInt()
        } else {
            targetHeight = maxDim
            targetWidth = (maxDim * ratio).toInt()
        }
        return Bitmap.createScaledBitmap(source, maxOf(targetWidth, 1), maxOf(targetHeight, 1), true)
    }

    fun stopCamera() {
        isStreaming = false
        try {
            cameraProvider?.unbindAll()
        } catch (e: Exception) {
            Log.e(TAG, "Lỗi unbind camera: ${e.message}", e)
        }
    }

    fun release() {
        stopCamera()
        cameraExecutor.shutdown()
    }
}