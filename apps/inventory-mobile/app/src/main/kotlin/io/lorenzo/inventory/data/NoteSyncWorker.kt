package io.lorenzo.inventory.data

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import io.lorenzo.inventory.InventoryApplication

class NoteSyncWorker(context: Context, parameters: WorkerParameters) :
    CoroutineWorker(context, parameters) {
    override suspend fun doWork(): Result {
        val repository = (applicationContext as InventoryApplication).repository
        return if (repository.syncNotes()) Result.success() else Result.retry()
    }
}
