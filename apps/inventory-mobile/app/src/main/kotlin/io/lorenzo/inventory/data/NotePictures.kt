package io.lorenzo.inventory.data

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.ImageDecoder
import android.net.Uri
import androidx.core.content.FileProvider
import java.io.ByteArrayOutputStream
import java.io.File
import kotlin.math.min
import kotlin.math.sqrt
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** The external camera's sole temporary plaintext output; draft bytes live encrypted in Room. */
object NotePictures {
    fun captureFile(context: Context, id: String): File {
        require(runCatching { java.util.UUID.fromString(id) }.isSuccess)
        return File(File(context.cacheDir, "captures").apply { mkdirs() }, "$id.jpg")
    }

    fun captureUri(context: Context, id: String): Uri =
        FileProvider.getUriForFile(
            context,
            "${context.packageName}.pictures",
            captureFile(context, id).apply { if (!exists()) createNewFile() },
        )

    fun removeCapture(context: Context, id: String) {
        val file = captureFile(context, id)
        runCatching {
            context.revokeUriPermission(
                FileProvider.getUriForFile(context, "${context.packageName}.pictures", file),
                android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION or
                    android.content.Intent.FLAG_GRANT_WRITE_URI_PERMISSION,
            )
        }
        file.delete()
    }

    fun clean(context: Context, keepId: String? = null) {
        File(context.cacheDir, "captures").listFiles()?.forEach {
            if (it.name != "${keepId}.jpg") {
                runCatching {
                    context.revokeUriPermission(
                        FileProvider.getUriForFile(context, "${context.packageName}.pictures", it),
                        android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION or
                            android.content.Intent.FLAG_GRANT_WRITE_URI_PERMISSION,
                    )
                }
                it.delete()
            }
        }
    }

    suspend fun normalize(context: Context, uri: Uri): ByteArray =
        withContext(Dispatchers.IO) {
            // ImageDecoder applies encoded orientation before the target dimensions are drawn.
            var bitmap =
                ImageDecoder.decodeBitmap(
                    ImageDecoder.createSource(context.contentResolver, uri)
                ) { decoder, info, _ ->
                    val width = info.size.width
                    val height = info.size.height
                    require(
                        width > 0 &&
                            height > 0 &&
                            width <= 32768 &&
                            height <= 32768 &&
                            width.toLong() * height <= 100_000_000
                    ) {
                        "This picture is too large"
                    }
                    val scale =
                        min(
                            1.0,
                            min(
                                4096.0 / maxOf(width, height),
                                sqrt(8_000_000.0 / (width.toDouble() * height)),
                            ),
                        )
                    decoder.allocator = ImageDecoder.ALLOCATOR_SOFTWARE
                    decoder.setTargetSize(
                        maxOf(1, (width * scale).toInt()),
                        maxOf(1, (height * scale).toInt()),
                    )
                    decoder.setOnPartialImageListener { false }
                }
            try {
                val opaque =
                    Bitmap.createBitmap(bitmap.width, bitmap.height, Bitmap.Config.ARGB_8888)
                Canvas(opaque).apply {
                    drawColor(Color.WHITE)
                    drawBitmap(bitmap, 0f, 0f, null)
                }
                bitmap.recycle()
                bitmap = opaque
                while (true) {
                    for (quality in listOf(92, 86, 80)) {
                        val output = ByteArrayOutputStream()
                        check(bitmap.compress(Bitmap.CompressFormat.JPEG, quality, output))
                        if (output.size() <= 2 * 1024 * 1024)
                            return@withContext output.toByteArray()
                    }
                    require(maxOf(bitmap.width, bitmap.height) > 1800) {
                        "This picture cannot fit without losing too much detail"
                    }
                    val smaller =
                        Bitmap.createScaledBitmap(
                            bitmap,
                            maxOf(1, (bitmap.width * .85).toInt()),
                            maxOf(1, (bitmap.height * .85).toInt()),
                            true,
                        )
                    bitmap.recycle()
                    bitmap = smaller
                }
                @Suppress("UNREACHABLE_CODE") error("No picture")
            } finally {
                bitmap.recycle()
            }
        }

    suspend fun preview(bytes: ByteArray, edge: Int = 1024): Bitmap =
        withContext(Dispatchers.Default) {
            ImageDecoder.decodeBitmap(ImageDecoder.createSource(java.nio.ByteBuffer.wrap(bytes))) {
                decoder,
                info,
                _ ->
                require(
                    info.size.width.toLong() * info.size.height <= 100_000_000 &&
                        info.size.width <= 32768 &&
                        info.size.height <= 32768
                )
                val scale = min(1.0, edge.toDouble() / maxOf(info.size.width, info.size.height))
                decoder.allocator = ImageDecoder.ALLOCATOR_SOFTWARE
                decoder.setTargetSize(
                    maxOf(1, (info.size.width * scale).toInt()),
                    maxOf(1, (info.size.height * scale).toInt()),
                )
                decoder.setOnPartialImageListener { false }
            }
        }
}

class PictureImportException :
    Exception(
        "This picture could not be added. Choose a complete image up to 100 megapixels; very detailed pictures may need a smaller copy."
    )
