package io.lorenzo.inventory

import android.app.Application
import androidx.room.Room
import androidx.work.*
import io.lorenzo.inventory.data.*
import java.util.concurrent.TimeUnit

class InventoryApplication : Application() {
    private val cipher by lazy { DeviceCipher() }
    val secrets by lazy { SecretStore(this, cipher) }
    private val database by lazy {
        Room.databaseBuilder(this, InventoryDatabase::class.java, "inventory.db").build()
    }
    val repository by lazy {
        InventoryRepository(
            database.inventoryDao(),
            secrets,
            cipher,
            BuildConfig.API_BASE_URL,
            scheduleNotes = ::scheduleNotes,
            cancelNotes = { WorkManager.getInstance(this).cancelUniqueWork("note-sync") },
        )
    }

    override fun onCreate() {
        super.onCreate()
        // Recover the crash window between persisting a draft and enqueuing work.
        if (secrets.token.value != null) scheduleNotes()
    }

    private fun scheduleNotes() {
        val work =
            OneTimeWorkRequestBuilder<NoteSyncWorker>()
                .setConstraints(
                    Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()
                )
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 15, TimeUnit.SECONDS)
                .build()
        WorkManager.getInstance(this)
            .enqueueUniqueWork("note-sync", ExistingWorkPolicy.APPEND_OR_REPLACE, work)
    }
}
