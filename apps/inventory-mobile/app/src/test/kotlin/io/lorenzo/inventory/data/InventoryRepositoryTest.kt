package io.lorenzo.inventory.data

import io.lorenzo.inventory.core.*
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import kotlinx.serialization.encodeToString
import okhttp3.mockwebserver.Dispatcher
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.RecordedRequest
import org.junit.Assert.*
import org.junit.Test

class InventoryRepositoryTest {
    private val character = Character("library", "character", "Ashfang")

    private class MemoryCredentials : CredentialStore {
        override val token = MutableStateFlow<String?>(null)

        override fun save(token: String) {
            this.token.value = token
        }

        override fun clear() {
            token.value = null
        }
    }

    private object TestCipher : PayloadCipher {
        override fun encrypt(value: String) = "test-encrypted:$value"

        override fun decrypt(value: String) = value.removePrefix("test-encrypted:")
    }

    private class MemoryDao : InventoryDao {
        val snapshots = MutableStateFlow<Map<String, Snapshot>>(emptyMap())
        val notes = MutableStateFlow<List<PendingNote>>(emptyList())

        val media = mutableListOf<MediaChunk>()
        val drafts = MutableStateFlow<List<StoredDraft>>(emptyList())

        override suspend fun putMedia(rows: List<MediaChunk>) {
            rows.forEach { row ->
                media.removeAll {
                    it.scope == row.scope && it.mediaId == row.mediaId && it.part == row.part
                }
                media.add(row)
            }
        }

        override suspend fun media(scope: String, id: String) =
            media.filter { it.scope == scope && it.mediaId == id }.sortedBy { it.part }

        override suspend fun removeMedia(scope: String, id: String) {
            media.removeAll { it.scope == scope && it.mediaId == id }
        }

        override suspend fun removeMediaScope(prefix: String) {
            media.removeAll { it.scope.startsWith(prefix) }
        }

        override suspend fun clearMedia() {
            media.clear()
        }

        override suspend fun putDraft(row: StoredDraft) {
            drafts.value = drafts.value.filterNot { it.scope == row.scope && it.id == row.id } + row
        }

        override suspend fun draft(scope: String, id: String) =
            drafts.value.firstOrNull { it.scope == scope && it.id == id }

        override fun observeDraft(scope: String, id: String) =
            drafts.map { rows -> rows.firstOrNull { it.scope == scope && it.id == id } }

        override suspend fun drafts(scope: String) = drafts.value.filter { it.scope == scope }

        override suspend fun removeDraft(scope: String, id: String) {
            drafts.value = drafts.value.filterNot { it.scope == scope && it.id == id }
        }

        override suspend fun clearDrafts() {
            drafts.value = emptyList()
        }

        override fun observe(key: String) = snapshots.map { it[key] }

        override suspend fun snapshot(key: String) = snapshots.value[key]

        override suspend fun put(row: Snapshot) {
            snapshots.value += row.key to row
        }

        override suspend fun remove(key: String) {
            snapshots.value -= key
        }

        override suspend fun clearSnapshots() {
            snapshots.value = emptyMap()
        }

        override fun observePending() = notes

        override suspend fun pending() = notes.value

        override suspend fun putNote(row: PendingNote) {
            notes.value = notes.value.filterNot { it.id == row.id } + row
        }

        override suspend fun removeNote(id: String) {
            notes.value = notes.value.filterNot { it.id == id }
        }

        override suspend fun clearNotes() {
            notes.value = emptyList()
        }
    }

    private suspend fun signedIn(
        server: MockWebServer
    ): Triple<InventoryRepository, MemoryDao, MemoryCredentials> {
        server.enqueue(
            MockResponse()
                .setBody(
                    """{"id":"user","players":[{"tenant_id":"library","characters":[{"entity_id":"character","name":"Ashfang"}]}]}"""
                )
        )
        val dao = MemoryDao()
        val credentials = MemoryCredentials()
        val repo =
            InventoryRepository(dao, credentials, TestCipher, server.url("/").toString(), {}, {})
        repo.login("lor_pat_test")
        server.takeRequest()
        return Triple(repo, dao, credentials)
    }

    @Test
    fun `a slow inventory request never blocks saving a local note`() = runBlocking {
        MockWebServer().use { server ->
            val (repo, dao) = signedIn(server)
            server.enqueue(
                MockResponse()
                    .setBody("""{"groups":[],"owners":[]}""")
                    .setBodyDelay(2, TimeUnit.SECONDS)
            )
            val refresh = launch(Dispatchers.Default) { repo.refreshInventory(character) }
            server.takeRequest()
            withTimeout(500) {
                repo.queueNote(character, "item", "Don't lose this", false, "en-US")
            }
            assertEquals(1, dao.notes.value.size)
            assertTrue(dao.notes.value.single().encrypted.startsWith("test-encrypted:"))
            refresh.cancelAndJoin()
        }
    }

    @Test
    fun `logout fences a response from the previous session`() = runBlocking {
        MockWebServer().use { server ->
            val (repo, dao, credentials) = signedIn(server)
            server.enqueue(
                MockResponse()
                    .setBody("""{"groups":[],"owners":[]}""")
                    .setBodyDelay(250, TimeUnit.MILLISECONDS)
            )
            val refresh = launch(Dispatchers.Default) { repo.refreshInventory(character) }
            server.takeRequest()
            repo.logout()
            refresh.join()
            assertNull(credentials.token.value)
            assertTrue(dao.snapshots.value.isEmpty())
            assertTrue(dao.notes.value.isEmpty())
        }
    }

    @Test
    fun `reader failure keeps the draft and retries the same note id`() = runBlocking {
        MockWebServer().use { server ->
            val (repo, dao) = signedIn(server)
            repo.queueNote(character, "item", "Remember the key", false, "de-DE")
            val id = dao.notes.value.single().id
            val note =
                """{"id":"$id","title":"Note","type":"note","is_public":false,"updated_at":"2026-10-13T00:00:00Z","payloads":[{"kind":"description","content":"Remember the key","locale":"de-DE"}]}"""
            server.enqueue(MockResponse().setResponseCode(201).setBody(note))
            server.enqueue(MockResponse().setResponseCode(503).setBody("""{"title":"Try again"}"""))
            assertFalse(repo.syncNotes())
            assertEquals(id, dao.notes.value.single().id)
            val original = server.takeRequest().body.readUtf8()
            server.takeRequest()
            server.enqueue(MockResponse().setBody(note))
            server.enqueue(MockResponse().setBody("{}"))
            server.enqueue(MockResponse().setBody("""{"items":[$note],"total":1}"""))
            assertTrue(repo.syncNotes())
            assertTrue(dao.notes.value.isEmpty())
            assertEquals(original, server.takeRequest().body.readUtf8())
            assertTrue(server.takeRequest().path!!.endsWith("/knowers/character"))
            server.takeRequest()
            assertEquals(id, repo.observeNotes(character, "item").first()!!.value.single().id)
        }
    }

    @Test
    fun `permanent note denial retains a recoverable draft`() = runBlocking {
        MockWebServer().use { server ->
            val (repo, dao) = signedIn(server)
            repo.queueNote(character, "item", "Draft", false, "en-US")
            server.enqueue(MockResponse().setResponseCode(403).setBody("""{"title":"Forbidden"}"""))
            assertTrue(repo.syncNotes())
            assertNotNull(dao.notes.value.single().error)
            repo.retryNote(dao.notes.value.single().id)
            assertNull(dao.notes.value.single().error)
        }
    }

    private class BundleServer(var loseResponses: Boolean = true) : Dispatcher() {
        var note: Information? = null
        var readers = Audience()
        var version = 1
        var uploadLost = false
        var orderLost = false
        var audienceLost = false
        var audienceWrites = 0
        var orderWrites = 0
        var reorderOnAppend = false
        val uploadIds = mutableListOf<String>()

        private fun reply(body: String = "{}", status: Int = 200) =
            MockResponse()
                .setResponseCode(status)
                .setHeader("ETag", "W/\"v$version\"")
                .setBody(body)

        override fun dispatch(request: RecordedRequest): MockResponse {
            val path = request.path.orEmpty()
            val body = request.body.readUtf8()
            if (path.endsWith("/editor"))
                return note?.let { reply(LorenzoJson.encodeToString(it)) } ?: reply(status = 404)
            if (path.endsWith("/information") && request.method == "POST") {
                val create = LorenzoJson.decodeFromString<NoteCreate>(body)
                check(!create.isPublic)
                note =
                    Information(
                        create.id,
                        "Note",
                        "note",
                        false,
                        "v$version",
                        payloads =
                            listOf(
                                Payload(
                                    "description",
                                    create.content,
                                    create.locale,
                                    "first",
                                    updatedAt = "v$version",
                                )
                            ),
                    )
                return reply(LorenzoJson.encodeToString(note))
            }
            if (path.endsWith("/payloads") && request.method == "POST") {
                val id =
                    body
                        .substringAfter("name=\"payload_id\"")
                        .substringAfter("\r\n\r\n")
                        .substringBefore("\r\n")
                uploadIds += id
                if (note!!.payloads.none { it.id == id }) {
                    version++
                    note =
                        note!!.copy(
                            payloads =
                                note!!.payloads +
                                    Payload("picture", id = id, updatedAt = "v$version")
                        )
                }
                if (loseResponses && !uploadLost) {
                    uploadLost = true
                    return reply(status = 503)
                }
                return reply()
            }
            if (path.endsWith("/texts")) {
                val text = LorenzoJson.decodeFromString<TextAppend>(body)
                if (note!!.payloads.none { it.id == text.id }) {
                    version++
                    note =
                        note!!.copy(
                            payloads =
                                note!!.payloads +
                                    Payload(
                                        "description",
                                        text.content,
                                        text.locale,
                                        text.id,
                                        updatedAt = "v$version",
                                    )
                        )
                }
                if (reorderOnAppend) note = note!!.copy(payloads = note!!.payloads.asReversed())
                return reply()
            }
            if (path.endsWith("/payloads/order")) {
                orderWrites++
                check(request.getHeader("If-Match") == "W/\"v$version\"")
                val order = LorenzoJson.decodeFromString<PayloadOrder>(body).payloadIds
                version++
                note =
                    note!!.copy(
                        payloads = order.map { id -> note!!.payloads.first { it.id == id } }
                    )
                if (loseResponses && !orderLost) {
                    orderLost = true
                    return reply(status = 503)
                }
                return reply()
            }
            if (path.endsWith("/audience")) {
                if (request.method == "PUT") {
                    check(request.getHeader("If-Match") == "W/\"v$version\"")
                    audienceWrites++
                    readers = LorenzoJson.decodeFromString(body)
                    version++
                    note = note!!.copy(isPublic = readers.isPublic)
                    if (loseResponses && !audienceLost) {
                        audienceLost = true
                        return reply(status = 503)
                    }
                }
                return reply(LorenzoJson.encodeToString(readers))
            }
            if (path.contains("/information?"))
                return reply(
                    LorenzoJson.encodeToString(
                        Page(listOfNotNull(note), if (note == null) 0 else 1)
                    )
                )
            return reply(status = 404)
        }
    }

    private suspend fun pictureDraft(repo: InventoryRepository) {
        repo.startComposer(character, "item", "en-US")
        repo.changeComposer(character, "item") {
            it.copy(parts = it.parts.map { part -> part.copy(text = "Map legend") })
        }
        val capture = repo.beginCapture(character, "item", false)
        repo.finishCapture(capture, ByteArray(130_000) { 42 })
        repo.changeComposer(character, "item") {
            it.copy(parts = it.parts.asReversed() + DraftPart(text = "After the sketch"))
        }
        repo.queueComposer(character, "item")
    }

    @Test
    fun `bundle queue recovers lost upload order and audience responses without duplicates`() =
        runBlocking {
            MockWebServer().use { server ->
                val (repo, dao) = signedIn(server)
                pictureDraft(repo)
                assertEquals(2, dao.media.size)
                assertTrue(dao.media.all { it.encrypted.startsWith("test-encrypted:") })
                val remote = BundleServer()
                server.dispatcher = remote
                repeat(3) {
                    assertFalse(repo.syncNotes())
                    assertEquals(1, dao.notes.value.size)
                    assertEquals(2, dao.media.size)
                    assertNotNull(
                        repo.observeQueue().first().single().draft.bundle!!.firstPayloadId
                    )
                }
                assertTrue(repo.syncNotes())
                assertTrue(dao.notes.value.isEmpty())
                assertEquals(
                    listOf("picture", "description", "description"),
                    remote.note!!.payloads.map { it.kind },
                )
                assertEquals(3, remote.note!!.payloads.map { it.id }.distinct().size)
                assertEquals(1, remote.uploadIds.distinct().size)
                assertEquals(Audience(entityIds = listOf(character.entityId)), remote.readers)
                assertEquals(1, remote.audienceWrites)
                assertTrue(dao.media.all { "/pictures/" in it.scope })
            }
        }

    @Test
    fun `a concurrent audience change retains the complete draft and never widens it`() =
        runBlocking {
            MockWebServer().use { server ->
                val (repo, dao) = signedIn(server)
                pictureDraft(repo)
                val remote =
                    BundleServer(false).apply {
                        readers = Audience(entityIds = listOf("someone-else"))
                    }
                server.dispatcher = remote
                assertTrue(repo.syncNotes())
                assertNotNull(dao.notes.value.single().error)
                assertEquals(0, remote.audienceWrites)
                assertEquals(listOf("someone-else"), remote.readers.entityIds)
                assertEquals(2, dao.media.size)
                assertEquals(3, repo.observeQueue().first().single().draft.bundle!!.parts.size)
            }
        }

    @Test
    fun `capture survives repository recreation and belongs to its original draft`() = runBlocking {
        MockWebServer().use { server ->
            val (repo, dao, credentials) = signedIn(server)
            repo.startComposer(character, "first-item", "en-US")
            val pending = repo.beginCapture(character, "first-item", true)
            val binding = requireNotNull(repo.markCaptureLaunched(pending.id))
            assertTrue(binding.launched)
            assertNull(repo.markCaptureLaunched(pending.id))
            repo.startComposer(character, "other-item", "en-US")
            repo.changeComposer(character, "first-item") {
                it.copy(parts = it.parts.map { part -> part.copy(text = "Latest words") })
            }
            val restored =
                InventoryRepository(
                    dao,
                    credentials,
                    TestCipher,
                    server.url("/").toString(),
                    {},
                    {},
                )
            assertEquals(binding, restored.capture())
            restored.finishCapture(binding, ByteArray(100) { 1 })
            val original = restored.observeComposer(character, "first-item").first()!!
            assertEquals("Latest words", original.parts.first().text)
            assertEquals("picture", original.parts.last().kind)
            assertEquals(1, restored.observeComposer(character, "other-item").first()!!.parts.size)
            assertNull(restored.capture())
            restored.finishCapture(binding, ByteArray(100) { 2 })
            assertEquals(1, dao.media.size)
            restored.logout()
            assertTrue(dao.media.isEmpty())
            assertTrue(dao.drafts.value.isEmpty())
        }
    }

    @Test
    fun `cancelled capture cannot append to a replacement composer`() = runBlocking {
        MockWebServer().use { server ->
            val (repo, dao) = signedIn(server)
            repo.startComposer(character, "item", "en-US")
            val old = repo.beginCapture(character, "item", false)
            repo.discardComposer(character, "item")
            repo.startComposer(character, "item", "en-US")
            assertNull(repo.markCaptureLaunched(old.id))
            repo.finishCapture(old, byteArrayOf(1, 2))
            assertEquals(1, repo.observeComposer(character, "item").first()!!.parts.size)
            assertTrue(dao.media.isEmpty())
        }
    }

    @Test
    fun `concurrent payload ordering is retained as a conflict`() = runBlocking {
        MockWebServer().use { server ->
            val (repo, dao) = signedIn(server)
            pictureDraft(repo)
            val remote = BundleServer(false).apply { reorderOnAppend = true }
            server.dispatcher = remote
            assertTrue(repo.syncNotes())
            assertNotNull(dao.notes.value.single().error)
            assertEquals(0, remote.orderWrites)
            assertEquals(2, dao.media.size)
        }
    }

    @Test
    fun `refresh removes protected picture bytes and fences an older download`() = runBlocking {
        MockWebServer().use { server ->
            val (repo, dao) = signedIn(server)
            val payload = Payload("picture", id = "picture", updatedAt = "version")
            val note = Information("note", "Note", "note", false, "v1", payloads = listOf(payload))
            val notes = LorenzoJson.encodeToString(Page(listOf(note), 1))
            server.enqueue(MockResponse().setBody(notes))
            repo.refreshNotes(character, "item")
            server.takeRequest()
            server.enqueue(MockResponse().setHeader("Content-Type", "image/jpeg").setBody("image"))
            repo.protectedPicture(character.tenantId, payload)
            server.takeRequest()
            assertTrue(dao.media.isNotEmpty())
            server.enqueue(
                MockResponse()
                    .setHeader("Content-Type", "image/jpeg")
                    .setBody("old image")
                    .setBodyDelay(300, TimeUnit.MILLISECONDS)
            )
            val old =
                async(Dispatchers.Default) { repo.protectedPicture(character.tenantId, payload) }
            server.takeRequest()
            server.enqueue(MockResponse().setBody("""{"items":[],"total":0}"""))
            repo.refreshNotes(character, "item")
            server.takeRequest()
            try {
                old.await()
                fail("Expected stale download cancellation")
            } catch (_: CancellationException) {}
            assertTrue(dao.media.isEmpty())
            withTimeout(500) {
                try {
                    repo.protectedPicture(character.tenantId, payload)
                    fail("Expected access refusal")
                } catch (_: java.io.IOException) {}
            }
            assertTrue(dao.media.isEmpty())
        }
    }
}
