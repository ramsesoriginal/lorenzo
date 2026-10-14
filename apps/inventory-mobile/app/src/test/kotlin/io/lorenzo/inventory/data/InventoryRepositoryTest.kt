package io.lorenzo.inventory.data

import io.lorenzo.inventory.core.*
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
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
}
