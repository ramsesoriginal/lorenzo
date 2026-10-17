package io.lorenzo.inventory.core

import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import okhttp3.Call
import okhttp3.Callback
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response

val LorenzoJson = Json {
    ignoreUnknownKeys = true
    encodeDefaults = true
}

private val SharedHttp =
    OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .callTimeout(45, TimeUnit.SECONDS)
        .followRedirects(false)
        .followSslRedirects(false)
        .retryOnConnectionFailure(false)
        .build()

class ApiException(val status: Int, val problem: Problem) : IOException(problem.title)

/**
 * Typed mobile adapter for the same REST contracts used by packages/api-client. A session owns one
 * client: its credential never follows arbitrary URLs or redirects.
 */
class LorenzoApi(
    baseUrl: String,
    private val token: String? = null,
    private val http: OkHttpClient = SharedHttp,
) {
    private val base =
        baseUrl.toHttpUrl().also {
            require(it.isHttps || (it.host in listOf("localhost", "127.0.0.1"))) {
                "API must use HTTPS"
            }
        }

    private data class Reply(val text: String, val etag: String, val picture: PictureBytes? = null)

    private suspend fun exchange(
        path: List<String>,
        method: String = "GET",
        body: RequestBody? = null,
        query: Map<String, String> = emptyMap(),
        ifMatch: String? = null,
        binary: Boolean = false,
    ): Reply {
        val url =
            base
                .newBuilder()
                .apply {
                    path.forEach(::addPathSegment)
                    query.forEach { (key, value) -> addQueryParameter(key, value) }
                }
                .build()
        val request =
            Request.Builder()
                .url(url)
                .header("Accept", if (binary) "image/*" else "application/json")
                .apply {
                    token?.let { header("Authorization", "Bearer $it") }
                    ifMatch?.let { header("If-Match", it) }
                    if (method != "GET") method(method, body)
                }
                .build()
        return suspendCancellableCoroutine { continuation ->
            val call = http.newCall(request)
            continuation.invokeOnCancellation { call.cancel() }
            call.enqueue(
                object : Callback {
                    override fun onFailure(call: Call, e: IOException) {
                        if (!continuation.isCancelled) continuation.resumeWithException(e)
                    }

                    override fun onResponse(call: Call, response: Response) {
                        try {
                            response.use {
                                val bytes =
                                    it.body.byteStream().use { stream ->
                                        val output = java.io.ByteArrayOutputStream()
                                        val buffer = ByteArray(16384)
                                        while (true) {
                                            val count = stream.read(buffer)
                                            if (count < 0) break
                                            if (output.size() + count > 10 * 1024 * 1024)
                                                throw IOException(
                                                    "Response exceeds the image limit"
                                                )
                                            output.write(buffer, 0, count)
                                        }
                                        output.toByteArray()
                                    }
                                if (!it.isSuccessful) {
                                    val problem =
                                        runCatching {
                                                LorenzoJson.decodeFromString<Problem>(
                                                    bytes.decodeToString()
                                                )
                                            }
                                            .getOrElse {
                                                Problem(title = "Request failed (${response.code})")
                                            }
                                    throw ApiException(it.code, problem)
                                }
                                val mime =
                                    it.body
                                        .contentType()
                                        ?.toString()
                                        ?.substringBefore(';')
                                        .orEmpty()
                                if (
                                    binary &&
                                        mime !in
                                            listOf(
                                                "image/png",
                                                "image/jpeg",
                                                "image/webp",
                                                "image/gif",
                                            )
                                )
                                    throw IOException("This payload is not a supported picture")
                                if (!continuation.isCancelled)
                                    continuation.resume(
                                        Reply(
                                            if (binary) "" else bytes.decodeToString(),
                                            it.header("ETag").orEmpty(),
                                            if (binary) PictureBytes(bytes, mime) else null,
                                        )
                                    )
                            }
                        } catch (error: Exception) {
                            if (!continuation.isCancelled) continuation.resumeWithException(error)
                        }
                    }
                }
            )
        }
    }

    private suspend fun request(
        path: List<String>,
        method: String = "GET",
        body: String? = null,
        query: Map<String, String> = emptyMap(),
    ): String =
        exchange(path, method, body?.toRequestBody("application/json".toMediaType()), query).text

    private fun info(tenantId: String, id: String) = listOf("tenants", tenantId, "information", id)

    private fun jsonBody(value: String) = value.toRequestBody("application/json".toMediaType())

    suspend fun editor(tenantId: String, id: String): Versioned<Information> {
        val reply = exchange(info(tenantId, id) + "editor")
        return Versioned(LorenzoJson.decodeFromString(reply.text), reply.etag)
    }

    suspend fun audience(tenantId: String, id: String): Versioned<Audience> {
        val reply = exchange(info(tenantId, id) + "audience")
        return Versioned(LorenzoJson.decodeFromString(reply.text), reply.etag)
    }

    suspend fun setAudience(tenantId: String, id: String, audience: Audience, etag: String) {
        exchange(
            info(tenantId, id) + "audience",
            "PUT",
            jsonBody(LorenzoJson.encodeToString(audience)),
            ifMatch = etag,
        )
    }

    suspend fun appendText(tenantId: String, id: String, text: TextAppend, etag: String) {
        exchange(
            info(tenantId, id) + "texts",
            "POST",
            jsonBody(LorenzoJson.encodeToString(text)),
            ifMatch = etag,
        )
    }

    suspend fun appendPicture(
        tenantId: String,
        id: String,
        payloadId: String,
        bytes: ByteArray,
        etag: String,
    ) {
        val body =
            MultipartBody.Builder()
                .setType(MultipartBody.FORM)
                .addFormDataPart("payload_id", payloadId)
                .addFormDataPart(
                    "file",
                    "picture.jpg",
                    bytes.toRequestBody("image/jpeg".toMediaType()),
                )
                .build()
        exchange(info(tenantId, id) + "payloads", "POST", body, ifMatch = etag)
    }

    suspend fun order(tenantId: String, id: String, ids: List<String>, etag: String) {
        exchange(
            info(tenantId, id) + listOf("payloads", "order"),
            "PUT",
            jsonBody(LorenzoJson.encodeToString(PayloadOrder(ids))),
            ifMatch = etag,
        )
    }

    suspend fun removePayload(tenantId: String, payloadId: String, etag: String) {
        exchange(listOf("tenants", tenantId, "payloads", payloadId), "DELETE", ifMatch = etag)
    }

    suspend fun picture(tenantId: String, payloadId: String): PictureBytes =
        requireNotNull(
            exchange(listOf("tenants", tenantId, "payloads", payloadId, "content"), binary = true)
                .picture
        )

    suspend fun recipients(tenantId: String): List<Recipient> {
        val all = mutableListOf<Recipient>()
        for (kind in listOf("characters", "groups")) {
            var page = 1
            var count = 0
            do {
                val text =
                    request(
                        listOf("tenants", tenantId, kind),
                        query = mapOf("page" to (page++).toString(), "size" to "100"),
                    )
                val result =
                    if (kind == "groups") {
                        val groups = LorenzoJson.decodeFromString<Page<EntityRef>>(text)
                        Page(groups.items.map { Recipient(it.id, it.name) }, groups.total)
                    } else LorenzoJson.decodeFromString<Page<Recipient>>(text)
                all += result.items
                count += result.items.size
                if (count >= result.total || result.items.isEmpty()) break
            } while (true)
        }
        return all.distinctBy { it.entityId }.sortedBy { it.name.lowercase() }
    }

    suspend fun me(): Me = LorenzoJson.decodeFromString(request(listOf("me")))

    suspend fun inventory(character: Character): Inventory =
        LorenzoJson.decodeFromString(
            request(
                listOf(
                    "tenants",
                    character.tenantId,
                    "item-instances",
                    "held-by",
                    character.entityId,
                )
            )
        )

    suspend fun notes(tenantId: String, itemId: String): List<Information> {
        val all = mutableListOf<Information>()
        var page = 1
        do {
            val result =
                LorenzoJson.decodeFromString<Page<Information>>(
                    request(
                        listOf("tenants", tenantId, "entities", itemId, "information"),
                        query =
                            mapOf("type" to "note", "page" to (page++).toString(), "size" to "100"),
                    )
                )
            all += result.items
            if (all.size >= result.total || result.items.isEmpty()) break
        } while (true)
        return all
    }

    suspend fun createNote(tenantId: String, itemId: String, note: NoteCreate): Information =
        LorenzoJson.decodeFromString(
            request(
                listOf("tenants", tenantId, "entities", itemId, "information"),
                "POST",
                LorenzoJson.encodeToString(note),
            )
        )

    suspend fun information(tenantId: String, id: String): Information =
        LorenzoJson.decodeFromString(request(listOf("tenants", tenantId, "information", id)))

    suspend fun addReader(tenantId: String, id: String, characterId: String) {
        request(listOf("tenants", tenantId, "information", id, "knowers", characterId), "PUT", "{}")
    }

    suspend fun beginDeviceLogin(): DeviceCode =
        LorenzoJson.decodeFromString(
            request(
                listOf("device-codes"),
                "POST",
                """{"client_name":"Lorenzo Inventory on Android"}""",
            )
        )

    suspend fun pollDevice(code: String): IssuedToken =
        LorenzoJson.decodeFromString(
            request(
                listOf("device-codes", "token"),
                "POST",
                LorenzoJson.encodeToString(mapOf("device_code" to code)),
            )
        )
}
