package com.example.digitalhuman.ui

import android.app.AlarmManager
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build
import java.util.Calendar

/**
 * Lên lịch nhắc nhở buổi học theo kế hoạch đã thống nhất giữa robot và bé.
 * Dùng AlarmManager (không cần thêm dependency) + NotificationChannel.
 * Bộ nhận [StudyReminderReceiver] kiểm tra đúng thứ trong tuần rồi mới thông báo.
 */
object ReminderScheduler {
    const val PREFS_NAME = "robo_setup_prefs"
    const val KEY_PLAN_DAYS = "plan_days"
    const val KEY_PLAN_TIME = "plan_time"
    const val KEY_COMPANION_NAME = "companion_name"

    private const val CHANNEL_ID = "study_reminder"
    private const val CHANNEL_NAME = "Nhắc nhở giờ học"
    private const val REQUEST_CODE = 4321
    private const val NOTIF_ID = 9001

    private val WEEKDAY_CODES = arrayOf("sun", "mon", "tue", "wed", "thu", "fri", "sat")

    fun ensureChannel(context: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (manager.getNotificationChannel(CHANNEL_ID) != null) return
        val channel = NotificationChannel(
            CHANNEL_ID, CHANNEL_NAME, NotificationManager.IMPORTANCE_DEFAULT
        ).apply { description = "Nhắc bé vào buổi học đã hẹn với nhân vật đồng hành" }
        manager.createNotificationChannel(channel)
    }

    /**
     * Lên lịch nhắc nhở. [weekdays] là mã thứ (mon..sun), [startTime] dạng "HH:MM".
     * Lịch lặp hằng ngày; bộ nhận tự lọc đúng thứ.
     */
    fun schedule(context: Context, weekdays: List<String>, startTime: String, companionName: String) {
        ensureChannel(context)
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val cleanDays = weekdays.map { it.trim().lowercase().take(3) }
            .filter { it in WEEKDAY_CODES }
        prefs.edit()
            .putString(KEY_PLAN_DAYS, cleanDays.joinToString(","))
            .putString(KEY_PLAN_TIME, startTime)
            .putString(KEY_COMPANION_NAME, companionName)
            .apply()
        if (cleanDays.isEmpty()) {
            cancel(context)
            return
        }
        val triggerAt = nextTriggerMillis(cleanDays, startTime) ?: return
        val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        alarmManager.setInexactRepeating(
            AlarmManager.RTC_WAKEUP,
            triggerAt,
            AlarmManager.INTERVAL_DAY,
            pendingIntent(context)
        )
    }

    fun cancel(context: Context) {
        val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        alarmManager.cancel(pendingIntent(context))
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE).edit()
            .remove(KEY_PLAN_DAYS)
            .remove(KEY_PLAN_TIME)
            .apply()
    }

    fun showNotification(context: Context, companionName: String) {
        ensureChannel(context)
        val openApp = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val contentIntent = PendingIntent.getActivity(
            context, REQUEST_CODE, openApp,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val notification = Notification.Builder(context, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle("Đến giờ học cùng $companionName rồi! 📚")
            .setContentText("Chạm để mở app và bắt đầu buổi học đã hẹn nhé!")
            .setAutoCancel(true)
            .setContentIntent(contentIntent)
            .build()
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        try {
            manager.notify(NOTIF_ID, notification)
        } catch (e: SecurityException) {
            // Thiếu quyền POST_NOTIFICATIONS (Android 13+) — bỏ qua an toàn.
        }
    }

    private fun pendingIntent(context: Context): PendingIntent {
        val intent = Intent(context, StudyReminderReceiver::class.java)
        return PendingIntent.getBroadcast(
            context, REQUEST_CODE, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
    }

    /** Giờ kích hoạt gần nhất trong các thứ đã chọn, tại [startTime] "HH:MM". */
    private fun nextTriggerMillis(days: List<String>, startTime: String): Long? {
        val parts = startTime.split(":")
        val hour = parts.getOrNull(0)?.toIntOrNull() ?: 19
        val minute = parts.getOrNull(1)?.toIntOrNull() ?: 0
        val now = Calendar.getInstance()
        for (offset in 0..7) {
            val candidate = (now.clone() as Calendar).apply {
                add(Calendar.DAY_OF_YEAR, offset)
                set(Calendar.HOUR_OF_DAY, hour)
                set(Calendar.MINUTE, minute)
                set(Calendar.SECOND, 0)
                set(Calendar.MILLISECOND, 0)
            }
            val code = WEEKDAY_CODES[candidate.get(Calendar.DAY_OF_WEEK) - 1]
            if (code in days && candidate.timeInMillis > now.timeInMillis) {
                return candidate.timeInMillis
            }
        }
        return null
    }
}

/** Bộ nhận alarm: chỉ thông báo nếu hôm nay là một ngày học đã thống nhất. */
class StudyReminderReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val prefs = context.getSharedPreferences(ReminderScheduler.PREFS_NAME, Context.MODE_PRIVATE)
        val daysRaw = prefs.getString(ReminderScheduler.KEY_PLAN_DAYS, "") ?: ""
        val days = daysRaw.split(",").map { it.trim() }.filter { it.isNotBlank() }
        if (days.isEmpty()) return
        val todayCode = WEEKDAY_CODES[Calendar.getInstance().get(Calendar.DAY_OF_WEEK) - 1]
        if (todayCode !in days) return
        val name = prefs.getString(ReminderScheduler.KEY_COMPANION_NAME, "bạn nhỏ") ?: "bạn nhỏ"
        ReminderScheduler.showNotification(context, name)
    }

    private companion object {
        val WEEKDAY_CODES = arrayOf("sun", "mon", "tue", "wed", "thu", "fri", "sat")
    }
}

/** Android xóa alarm sau khi khởi động lại; dựng lại lịch đã được phụ huynh/bé bật. */
class StudyReminderBootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_BOOT_COMPLETED && intent.action != Intent.ACTION_MY_PACKAGE_REPLACED) return
        val prefs = context.getSharedPreferences(ReminderScheduler.PREFS_NAME, Context.MODE_PRIVATE)
        val days = prefs.getString(ReminderScheduler.KEY_PLAN_DAYS, "")
            ?.split(",")?.filter { it.isNotBlank() } ?: emptyList()
        if (days.isEmpty()) return
        ReminderScheduler.schedule(
            context,
            days,
            prefs.getString(ReminderScheduler.KEY_PLAN_TIME, "19:00") ?: "19:00",
            prefs.getString(ReminderScheduler.KEY_COMPANION_NAME, "Dora") ?: "Dora",
        )
    }
}
