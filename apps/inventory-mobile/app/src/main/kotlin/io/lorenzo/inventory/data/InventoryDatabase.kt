package io.lorenzo.inventory.data

import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.RoomDatabase
import androidx.room.Transaction
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase
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

@Entity(tableName = "media_chunks", primaryKeys = ["scope", "mediaId", "part"])
data class MediaChunk(val scope: String, val mediaId: String, val part: Int, val encrypted: String)

@Entity(tableName = "information_drafts", primaryKeys = ["scope", "id"])
data class StoredDraft(val scope: String, val id: String, val encrypted: String)

@Dao
interface InventoryDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun putMedia(rows: List<MediaChunk>)

    @Query("SELECT * FROM media_chunks WHERE scope = :scope AND mediaId = :id ORDER BY part")
    suspend fun media(scope: String, id: String): List<MediaChunk>

    @Query("DELETE FROM media_chunks WHERE scope = :scope AND mediaId = :id")
    suspend fun removeMedia(scope: String, id: String)

    @Query("DELETE FROM media_chunks WHERE scope LIKE :prefix || '%'")
    suspend fun removeMediaScope(prefix: String)

    @Query("DELETE FROM media_chunks") suspend fun clearMedia()

    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun putDraft(row: StoredDraft)

    @Query("SELECT * FROM information_drafts WHERE scope = :scope AND id = :id")
    suspend fun draft(scope: String, id: String): StoredDraft?

    @Query("SELECT * FROM information_drafts WHERE scope = :scope AND id = :id")
    fun observeDraft(scope: String, id: String): Flow<StoredDraft?>

    @Query("SELECT * FROM information_drafts WHERE scope = :scope")
    suspend fun drafts(scope: String): List<StoredDraft>

    @Query("DELETE FROM information_drafts WHERE scope = :scope AND id = :id")
    suspend fun removeDraft(scope: String, id: String)

    @Query("DELETE FROM information_drafts") suspend fun clearDrafts()

    @Transaction
    suspend fun stage(rows: List<MediaChunk>, draft: StoredDraft) {
        putMedia(rows)
        putDraft(draft)
    }

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

@Database(
    entities = [Snapshot::class, PendingNote::class, MediaChunk::class, StoredDraft::class],
    version = 2,
    exportSchema = true,
)
abstract class InventoryDatabase : RoomDatabase() {
    abstract fun inventoryDao(): InventoryDao
}

val InventoryMigration1To2 =
    object : Migration(1, 2) {
        override fun migrate(db: SupportSQLiteDatabase) {
            db.execSQL(
                "CREATE TABLE IF NOT EXISTS media_chunks (scope TEXT NOT NULL, mediaId TEXT NOT NULL, part INTEGER NOT NULL, encrypted TEXT NOT NULL, PRIMARY KEY(scope, mediaId, part))"
            )
            db.execSQL(
                "CREATE TABLE IF NOT EXISTS information_drafts (scope TEXT NOT NULL, id TEXT NOT NULL, encrypted TEXT NOT NULL, PRIMARY KEY(scope, id))"
            )
        }
    }
