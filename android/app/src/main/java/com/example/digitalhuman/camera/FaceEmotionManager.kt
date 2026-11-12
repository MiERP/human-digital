package com.example.digitalhuman.camera

import android.annotation.SuppressLint
import android.content.Context
import android.util.Log
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleOwner
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.face.FaceDetection
import com.google.mlkit.vision.face.FaceDetector
import com.google.mlkit.vision.face.FaceDetectorOptions
import java.util.concurrent.Executors

/**
 * Quản lý "Đôi Mắt Cảm Xúc" (Edge AI Emotional Vision) của Doraemon:
 * - Chạy ngầm phân tích khuôn mặt bé qua Camera trước bằng Google ML Kit.
 * - Xử lý 100% CỤC BỘ trên chip máy, KHÔNG gửi bất kỳ hình ảnh nào qua mạng (COPPA/GDPR).
 * - Tần số phân tích: 4 FPS (250ms / frame) với độ trễ phản hồi < 1.0 giây.
 * - Đa tầng nhận diện cảm xúc:
 *   + super_happy: Cười lớn, rạng rỡ, thích thú
 *   + happy: Mỉm cười, vui vẻ, tươi tắn
 *   + curious: Nghiêng đầu tò mò, suy nghĩ
 *   + attentive: Nhìn thẳng, chăm chú lắng nghe Doraemon
 *   + focused: Cúi đầu tập trung nhìn sách/bài tập
 *   + distracted: Quay đầu nhìn quanh, lơ đãng
 *   + sleepy: Mắt nhắm li bì, buồn ngủ
 *   + no_face: Không phát hiện bé trước ống kính
 */
class FaceEmotionManager(
    private val context: Context,
    private val onEmotionDetected: (emotion: String, confidence: Float) -> Unit
) {
    companion object {
        private const val TAG = "FaceEmotionManager"
        private const val INFERENCE_INTERVAL_MS = 250L // 4 FPS - Cực nhanh & siêu mượt
        private const val WINDOW_SIZE = 4 // Cửa sổ 1 giây để khử nhiễu chớp mắt
    }

    private val analysisExecutor = Executors.newSingleThreadExecutor()
    private var detector: FaceDetector? = null
    private var cameraProvider: ProcessCameraProvider? = null
    private var isAnalyzing = false
    private var lastAnalysisTimestamp = 0L
    private var lastEmittedEmotion = ""
    private var lastEmitTime = 0L

    // Bộ đệm trượt 4 khung hình gần nhất (~1 giây)
    private val emotionHistory = ArrayDeque<String>(WINDOW_SIZE + 2)

    init {
        // Cấu hình ML Kit Fast Mode tối ưu hóa cho vi xử lý di động
        val options = FaceDetectorOptions.Builder()
            .setPerformanceMode(FaceDetectorOptions.PERFORMANCE_MODE_FAST)
            .setClassificationMode(FaceDetectorOptions.CLASSIFICATION_MODE_ALL) // Nhận diện nụ cười & độ mở mắt
            .setLandmarkMode(FaceDetectorOptions.LANDMARK_MODE_NONE)
            .setContourMode(FaceDetectorOptions.CONTOUR_MODE_NONE)
            .setMinFaceSize(0.12f)
            .build()
        detector = FaceDetection.getClient(options)
    }

    fun startEmotionAnalysis(lifecycleOwner: LifecycleOwner) {
        if (isAnalyzing) return
        isAnalyzing = true
        emotionHistory.clear()
        lastEmittedEmotion = ""

        val cameraProviderFuture = ProcessCameraProvider.getInstance(context)
        cameraProviderFuture.addListener({
            try {
                cameraProvider = cameraProviderFuture.get()
                bindCamera(lifecycleOwner)
            } catch (e: Exception) {
                Log.e(TAG, "Lỗi khởi động Edge AI Emotion Analysis: ${e.message}", e)
            }
        }, ContextCompat.getMainExecutor(context))
    }

    fun stopEmotionAnalysis() {
        isAnalyzing = false
        emotionHistory.clear()
        try {
            cameraProvider?.unbindAll()
        } catch (e: Exception) {
            Log.e(TAG, "Lỗi dừng camera analysis: ${e.message}", e)
        }
    }

    fun release() {
        stopEmotionAnalysis()
        analysisExecutor.shutdown()
        detector?.close()
        detector = null
    }

    private fun bindCamera(lifecycleOwner: LifecycleOwner) {
        val provider = cameraProvider ?: return
        provider.unbindAll()

        val cameraSelector = CameraSelector.DEFAULT_FRONT_CAMERA

        // Phân tích ảnh ở độ phân giải thấp (360p) để đạt tốc độ cao nhất
        val imageAnalysis = ImageAnalysis.Builder()
            .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
            .build()

        imageAnalysis.setAnalyzer(analysisExecutor) { imageProxy ->
            processImageProxy(imageProxy)
        }

        try {
            provider.bindToLifecycle(
                lifecycleOwner,
                cameraSelector,
                imageAnalysis
            )
            Log.i(TAG, "Đôi Mắt Cảm Xúc Edge AI đã khởi động thành công trên Camera trước.")
        } catch (e: Exception) {
            Log.e(TAG, "Không thể liên kết Camera trước với ML Kit: ${e.message}", e)
        }
    }

    @SuppressLint("UnsafeOptInUsageError")
    private fun processImageProxy(imageProxy: ImageProxy) {
        if (!isAnalyzing) {
            imageProxy.close()
            return
        }

        val now = System.currentTimeMillis()
        if (now - lastAnalysisTimestamp < INFERENCE_INTERVAL_MS) {
            imageProxy.close()
            return
        }
        lastAnalysisTimestamp = now

        val mediaImage = imageProxy.image
        val detectorInstance = detector

        if (mediaImage != null && detectorInstance != null) {
            val rotationDegrees = imageProxy.imageInfo.rotationDegrees
            val image = InputImage.fromMediaImage(mediaImage, rotationDegrees)

            detectorInstance.process(image)
                .addOnSuccessListener { faces ->
                    if (faces.isNotEmpty()) {
                        val face = faces[0]
                        val smileProb = face.smilingProbability ?: -1f
                        val leftEye = face.leftEyeOpenProbability ?: -1f
                        val rightEye = face.rightEyeOpenProbability ?: -1f
                        val pitch = face.headEulerAngleX // Cúi xuống (<0) / Ngửa lên (>0)
                        val yaw = face.headEulerAngleY   // Quay trái (<0) / Quay phải (>0)
                        val roll = face.headEulerAngleZ  // Nghiêng đầu sang bên

                        val rawEmotion = classifyRawFrame(smileProb, leftEye, rightEye, pitch, yaw, roll)

                        // Đưa vào sliding window
                        emotionHistory.addLast(rawEmotion)
                        while (emotionHistory.size > WINDOW_SIZE) {
                            emotionHistory.removeFirst()
                        }

                        // Làm mượt (Temporal Smoothing) qua đa số phiếu trong 1 giây
                        val (smoothedEmotion, confidence) = computeSmoothedEmotion()

                        val timeSinceLastEmit = now - lastEmitTime
                        if (smoothedEmotion != lastEmittedEmotion || timeSinceLastEmit >= 3000L) {
                            lastEmittedEmotion = smoothedEmotion
                            lastEmitTime = now
                            Log.d(TAG, "Child emotion detected: $smoothedEmotion (confidence=$confidence, smile=$smileProb, yaw=$yaw, pitch=$pitch, roll=$roll)")
                            onEmotionDetected(smoothedEmotion, confidence)
                        }
                    } else {
                        emotionHistory.clear()
                        if (lastEmittedEmotion != "no_face") {
                            lastEmittedEmotion = "no_face"
                            lastEmitTime = now
                            onEmotionDetected("no_face", 0.0f)
                        }
                    }
                }
                .addOnFailureListener { e ->
                    Log.e(TAG, "Lỗi phân tích khuôn mặt: ${e.message}")
                }
                .addOnCompleteListener {
                    imageProxy.close()
                }
        } else {
            imageProxy.close()
        }
    }

    /**
     * Phân loại đa tầng cảm xúc & hành vi từ các góc độ khuôn mặt.
     */
    private fun classifyRawFrame(
        smileProb: Float,
        leftEye: Float,
        rightEye: Float,
        pitch: Float,
        yaw: Float,
        roll: Float
    ): String {
        val avgEyeOpen = if (leftEye >= 0 && rightEye >= 0) (leftEye + rightEye) / 2f else 0.8f

        return when {
            // 1. Cười rạng rỡ / Thích thú
            smileProb >= 0.65f -> "super_happy"

            // 2. Mỉm cười / Vui vẻ thân thiện
            smileProb in 0.30f..0.65f -> "happy"

            // 3. Mắt nhắm li bì (Mệt mỏi / Buồn ngủ)
            avgEyeOpen in 0.0f..0.22f -> "eye_closed"

            // 4. Nghiêng đầu tò mò / Thắc mắc
            Math.abs(roll) > 11.0f && smileProb < 0.25f -> "curious"

            // 5. Cúi đầu nhìn sách/vở (Tập trung làm bài)
            pitch < -16.0f -> "focused"

            // 6. Quay đầu sang bên cạnh (Mất tập trung / Nhìn quanh)
            Math.abs(yaw) > 22.0f -> "distracted"

            // 7. Nhìn thẳng vào màn hình chăm chú lắng nghe
            Math.abs(yaw) <= 15.0f && Math.abs(pitch) <= 15.0f && avgEyeOpen >= 0.40f -> "attentive"

            // 8. Trạng thái tự nhiên
            else -> "attentive"
        }
    }

    /**
     * Tính toán cảm xúc ổn định qua đa số phiếu trong cửa sổ 4 frames (~1 giây).
     */
    private fun computeSmoothedEmotion(): Pair<String, Float> {
        if (emotionHistory.isEmpty()) return Pair("attentive", 0.9f)

        val counts = mutableMapOf<String, Int>()
        for (e in emotionHistory) {
            counts[e] = (counts[e] ?: 0) + 1
        }
        val total = emotionHistory.size.toFloat()

        // Ưu tiên các cảm xúc mạnh & tích cực
        val superHappy = counts["super_happy"] ?: 0
        if (superHappy >= 2) return Pair("super_happy", superHappy / total)

        val happy = counts["happy"] ?: 0
        if (happy + superHappy >= 2) return Pair("happy", (happy + superHappy) / total)

        val closed = counts["eye_closed"] ?: 0
        if (closed >= 3) return Pair("sleepy", closed / total)

        val curious = counts["curious"] ?: 0
        if (curious >= 2) return Pair("curious", curious / total)

        val focused = counts["focused"] ?: 0
        if (focused >= 2) return Pair("focused", focused / total)

        val distracted = counts["distracted"] ?: 0
        if (distracted >= 2) return Pair("distracted", distracted / total)

        return Pair("attentive", (counts["attentive"] ?: 0) / total.coerceAtLeast(1.0f))
    }
}
