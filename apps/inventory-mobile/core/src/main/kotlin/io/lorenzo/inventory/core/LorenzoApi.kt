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
import okhttp3.OkHttpClient
import okhttp3.Request
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

    private suspend fun request(
        path: List<String>,
        method: String = "GET",
        body: String? = null,
        query: Map<String, String> = emptyMap(),
    ): String {
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
                .header("Accept", "application/json")
                .apply {
                    token?.let { header("Authorization", "Bearer $it") }
                    if (method != "GET")
                        method(method, body?.toRequestBody("application/json".toMediaType()))
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
                                val text = it.body.string()
                                if (it.isSuccessful) continuation.resume(text)
                                else {
                                    val problem =
                                        runCatching { LorenzoJson.decodeFromString<Problem>(text) }
                                            .getOrElse {
                                                Problem(title = "Request failed (${response.code})")
                                            }
                                    continuation.resumeWithException(ApiException(it.code, problem))
                                }
                            }
                        } catch (error: IOException) {
                            if (!continuation.isCancelled) continuation.resumeWithException(error)
                        }
                    }
                }
            )
        }
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
