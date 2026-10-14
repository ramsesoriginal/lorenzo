package io.lorenzo.inventory.core

import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.JsonPrimitive
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.Assert.*
import org.junit.Test

class LorenzoApiTest {
    @Test
    fun `roster includes co-piloted characters and deduplicates across campaigns within a library`() {
        val a = CharacterSummary("char-a", "Ashfang")
        val me =
            Me(
                "user",
                listOf(
                    Seat("library-a", listOf(a)),
                    Seat("library-a", listOf(a)),
                    Seat("library-b", listOf(a)),
                ),
            )
        assertEquals(listOf("library-a/char-a", "library-b/char-a"), me.characters().map { it.key })
    }

    @Test
    fun `locale uses exact match before language fallback`() {
        val item =
            Item(
                "id",
                "Sword",
                descriptions =
                    listOf(Description("English", "en-US"), Description("Deutsch", "de-DE")),
            )
        assertEquals("Deutsch", item.description(listOf("de-AT", "en-US"))?.content)
    }

    @Test
    fun `own and inherited descriptions are each retained in the preferred language`() {
        val parent = EntityRef("prototype", "Longsword")
        val item =
            Item(
                "instance",
                "Ashfang's blade",
                descriptions =
                    listOf(
                        Description("This one has a blue hilt.", "en-US"),
                        Description("Standard sword rules.", "en-US", parent),
                        Description("Schwertregeln.", "de-DE", parent),
                    ),
            )
        assertEquals(
            listOf("This one has a blue hilt.", "Schwertregeln."),
            item.descriptionsFor(listOf("de-DE")).map { it.content },
        )
    }

    @Test
    fun `unknown fields and zero stats survive decoding`() {
        val item =
            LorenzoJson.decodeFromString<Item>(
                """{"entity_id":"i","title":"Pouch","quantity":0,"physical_stats":[{"name":"weight","value":0}],"future_field":true}"""
            )
        assertEquals(JsonPrimitive(0), item.stats.single().value)
        assertEquals(0, item.quantity)
    }

    @Test
    fun `false tags retain their actual value in the stats`() {
        val item =
            LorenzoJson.decodeFromString<Item>(
                """{"entity_id":"i","title":"Sword","tags":[{"name":"cursed","value":false}]}"""
            )
        assertEquals(false, item.tags.single().value)
        assertEquals(JsonPrimitive(false), item.stats.single().value)
    }

    @Test
    fun `inventory calls actual holder route with bearer credential`() = runBlocking {
        MockWebServer().use { server ->
            server.enqueue(MockResponse().setBody("""{"groups":[],"owners":[]}"""))
            val api = LorenzoApi(server.url("/").toString(), "lor_pat_test")
            assertTrue(api.inventory(Character("library", "character", "Name")).items.isEmpty())
            val request = server.takeRequest()
            assertEquals("/tenants/library/item-instances/held-by/character", request.path)
            assertEquals("Bearer lor_pat_test", request.getHeader("Authorization"))
        }
    }

    @Test
    fun `notes fetch every page and preserve unknown payload kinds`() = runBlocking {
        MockWebServer().use { server ->
            val rows = (1..100).joinToString(",") { note(it.toString()) }
            server.enqueue(MockResponse().setBody("""{"items":[$rows],"total":101}"""))
            server.enqueue(MockResponse().setBody("""{"items":[${note("101")}],"total":101}"""))
            val notes = LorenzoApi(server.url("/").toString(), "token").notes("library", "item")
            assertEquals(101, notes.size)
            assertEquals("future", notes.first().payloads.single().kind)
            assertTrue(server.takeRequest().path!!.contains("type=note&page=1&size=100"))
            assertTrue(server.takeRequest().path!!.contains("page=2"))
        }
    }

    @Test
    fun `private note request uses stable client id and adds character reader separately`() =
        runBlocking {
            MockWebServer().use { server ->
                server.enqueue(MockResponse().setResponseCode(201).setBody(note("stable-id")))
                server.enqueue(MockResponse().setResponseCode(200).setBody(note("stable-id")))
                server.enqueue(MockResponse().setResponseCode(200).setBody("{}"))
                val api = LorenzoApi(server.url("/").toString(), "token")
                val request =
                    NoteCreate("stable-id", content = "Remember the key", locale = "de-DE")
                api.createNote("library", "item", request)
                api.createNote("library", "item", request)
                api.addReader("library", "stable-id", "character")
                val first = server.takeRequest().body.readUtf8()
                val replay = server.takeRequest().body.readUtf8()
                assertEquals(first, replay)
                assertTrue(first.contains("\"is_public\":false"))
                assertTrue(first.contains("\"id\":\"stable-id\""))
                val reader = server.takeRequest()
                assertEquals("PUT", reader.method)
                assertEquals(
                    "/tenants/library/information/stable-id/knowers/character",
                    reader.path,
                )
            }
        }

    @Test
    fun `API errors expose status and problem type without credential`() = runBlocking {
        MockWebServer().use { server ->
            server.enqueue(
                MockResponse()
                    .setResponseCode(401)
                    .setBody("""{"type":"invalid-token","title":"Sign in again"}""")
            )
            try {
                LorenzoApi(server.url("/").toString(), "secret").me()
                fail("Expected 401")
            } catch (error: ApiException) {
                assertEquals(401, error.status)
                assertEquals("invalid-token", error.problem.type)
                assertFalse(error.message!!.contains("secret"))
            }
        }
    }

    @Test
    fun `authenticated requests never follow redirects to another origin`() = runBlocking {
        MockWebServer().use { first ->
            MockWebServer().use { second ->
                first.enqueue(
                    MockResponse().setResponseCode(302).setHeader("Location", second.url("/"))
                )
                try {
                    LorenzoApi(first.url("/").toString(), "secret").me()
                    fail("Expected redirect refusal")
                } catch (error: ApiException) {
                    assertEquals(302, error.status)
                }
                assertEquals(0, second.requestCount)
            }
        }
    }

    private fun note(id: String) =
        """{"id":"$id","title":"Note","type":"note","is_public":false,"updated_at":"2026-10-13T00:00:00Z","payloads":[{"kind":"future","other":123}]}"""
}
