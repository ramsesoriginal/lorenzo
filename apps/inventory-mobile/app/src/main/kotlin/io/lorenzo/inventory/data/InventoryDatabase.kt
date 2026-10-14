package io.lorenzo.inventory.data

import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.RoomDatabase
import kotlinx.coroutines.flow.Flow

@Entity(tableName = "snapshots")
data class Snapshot(@PrimaryKey val key: String, val encrypted: String, val updatedAt: Long)

@Entity(tableName = "pending_notes")
data class PendingNote(
    @PrimaryKey val id: String,
    val encrypted: String,
    val error: String? = null,
    val createdAt: Long = System.currentTimeMillis(),
)

@Dao
interface InventoryDao {
    @Query("SELECT * FROM snapshots WHERE `key` = :key") fun observe(key: String): Flow<Snapshot?>

    @Query("SELECT * FROM snapshots WHERE `key` = :key")
    suspend fun snapshot(key: String): Snapshot?

    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun put(row: Snapshot)

    @Query("DELETE FROM snapshots WHERE `key` = :key") suspend fun remove(key: String)

    @Query("DELETE FROM snapshots") suspend fun clearSnapshots()

    @Query("SELECT * FROM pending_notes ORDER BY createdAt")
    fun observePending(): Flow<List<PendingNote>>

    @Query("SELECT * FROM pending_notes ORDER BY createdAt")
    suspend fun pending(): List<PendingNote>

    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun putNote(row: PendingNote)

    @Query("DELETE FROM pending_notes WHERE id = :id") suspend fun removeNote(id: String)

    @Query("DELETE FROM pending_notes") suspend fun clearNotes()
}

@Database(entities = [Snapshot::class, PendingNote::class], version = 1, exportSchema = true)
abstract class InventoryDatabase : RoomDatabase() {
    abstract fun inventoryDao(): InventoryDao
}
