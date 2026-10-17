package io.lorenzo.inventory

import android.graphics.Bitmap
import android.graphics.Color
import androidx.room.Room
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import io.lorenzo.inventory.data.*
import java.io.ByteArrayOutputStream
import java.util.UUID
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class NotePicturesTest {
    private val context
        get() = InstrumentationRegistry.getInstrumentation().targetContext

    @Test
    fun cameraOutputIsOrientedAndNormalizedWithoutChangingOriginal() = runBlocking {
        val bitmap =
            Bitmap.createBitmap(40, 20, Bitmap.Config.ARGB_8888).apply { eraseColor(Color.RED) }
        val output = ByteArrayOutputStream()
        bitmap.compress(Bitmap.CompressFormat.JPEG, 95, output)
        bitmap.recycle()
        val jpeg = output.toByteArray()
        // EXIF little-endian TIFF orientation=6: the camera's encoded pixels turn clockwise.
        val exif =
            byteArrayOf(
                69,
                120,
                105,
                102,
                0,
                0,
                73,
                73,
                42,
                0,
                8,
                0,
                0,
                0,
                1,
                0,
                18,
                1,
                3,
                0,
                1,
                0,
                0,
                0,
                6,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
            )
        val original =
            jpeg.copyOfRange(0, 2) +
                byteArrayOf(0xff.toByte(), 0xe1.toByte(), 0, (exif.size + 2).toByte()) +
                exif +
                jpeg.copyOfRange(2, jpeg.size)
        val id = UUID.randomUUID().toString()
        val file = NotePictures.captureFile(context, id).apply { writeBytes(original) }
        try {
            val bytes = NotePictures.normalize(context, NotePictures.captureUri(context, id))
            assertTrue(bytes.size <= 2 * 1024 * 1024)
            assertArrayEquals(original, file.readBytes())
            val oriented = NotePictures.preview(bytes)
            assertEquals(20, oriented.width)
            assertEquals(40, oriented.height)
            oriented.recycle()
            assertTrue(
                NotePictures.captureUri(context, id)
                    .toString()
                    .startsWith("content://${context.packageName}.pictures/")
            )
        } finally {
            NotePictures.clean(context)
        }
    }

    @Test
    fun migrationKeepsExistingEncryptedDraftsAndAddsChunkStorage() = runBlocking {
        val name = "migration-${UUID.randomUUID()}.db"
        context.openOrCreateDatabase(name, 0, null).use { db ->
            db.execSQL(
                "CREATE TABLE snapshots (`key` TEXT NOT NULL, encrypted TEXT NOT NULL, updatedAt INTEGER NOT NULL, PRIMARY KEY(`key`))"
            )
            db.execSQL(
                "CREATE TABLE pending_notes (id TEXT NOT NULL, encrypted TEXT NOT NULL, error TEXT, createdAt INTEGER NOT NULL, PRIMARY KEY(id))"
            )
            db.execSQL("INSERT INTO pending_notes VALUES ('note','encrypted-draft',NULL,1)")
            db.version = 1
        }
        val db =
            Room.databaseBuilder(context, InventoryDatabase::class.java, name)
                .addMigrations(InventoryMigration1To2)
                .build()
        try {
            assertEquals("encrypted-draft", db.inventoryDao().pending().single().encrypted)
            db.inventoryDao()
                .putMedia(listOf(MediaChunk("account", "picture", 0, "encrypted-bytes")))
            assertEquals(
                "encrypted-bytes",
                db.inventoryDao().media("account", "picture").single().encrypted,
            )
        } finally {
            db.close()
            context.deleteDatabase(name)
        }
    }
}
