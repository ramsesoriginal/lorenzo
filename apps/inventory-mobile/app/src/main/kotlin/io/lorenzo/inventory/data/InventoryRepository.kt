package io.lorenzo.inventory.data

import io.lorenzo.inventory.core.*
import java.io.IOException
import java.security.MessageDigest
import java.util.UUID
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString

@Serializable
data class NoteDraft(val character: Character, val itemId: String, val request: NoteCreate)

data class QueuedNote(val id: String, val draft: NoteDraft, val error: String?)

data class Cached<T>(val value: T, val updatedAt: Long)

class InventoryRepository(
    private val dao: InventoryDao,
    private val secrets: CredentialStore,
    private val cipher: PayloadCipher,
    private val apiUrl: String,
    private val scheduleNotes: () -> Unit,
    private val cancelNotes: () -> Unit,
) {
    // Only session transitions and persistence serialize. Network work never holds
    // this mutex: saving a local draft does not wait for a slow inventory request.
    private val lock = Mutex()
    private val syncLock = Mutex()
    private val noteRevisions = mutableMapOf<String, Long>()

    private suspend fun noteRevision(session: Session, suffix: String): Long =
        lock.withLock {
            if (!sameSession(session)) throw CancellationException("Session changed")
            val key = session.key(suffix)
            ((noteRevisions[key] ?: 0) + 1).also { noteRevisions[key] = it }
        }

    private data class Session(val token: String) {
        val key: String =
            MessageDigest.getInstance("SHA-256").digest(token.toByteArray()).joinToString("") {
                "%02x".format(it)
            }

        fun key(suffix: String) = "$key/$suffix"
    }

    private fun currentSession() = secrets.token.value?.let(::Session)

    private suspend fun session() = lock.withLock { requireNotNull(currentSession()) }

    private fun sameSession(session: Session) = secrets.token.value == session.token

    private fun key(suffix: String) = currentSession()?.key(suffix) ?: "signed-out/$suffix"

    private fun notesKey(character: Character, itemId: String) =
        "notes/${character.tenantId}/$itemId"

    private inline fun <reified T> observe(suffix: String) =
        dao.observe(key(suffix))
            .map { row ->
                row?.let {
                    Cached(
                        LorenzoJson.decodeFromString<T>(cipher.decrypt(it.encrypted)),
                        it.updatedAt,
                    )
                }
            }
            .flowOn(Dispatchers.Default)

    fun observeMe() = observe<Me>("me")

    fun observeInventory(character: Character) = observe<Inventory>("inventory/${character.key}")

    fun observeNotes(character: Character, itemId: String) =
        observe<List<Information>>(notesKey(character, itemId))

    fun observeQueue() =
        dao.observePending()
            .map { rows ->
                rows.map {
                    QueuedNote(
                        it.id,
                        LorenzoJson.decodeFromString<NoteDraft>(cipher.decrypt(it.encrypted)),
                        it.error,
                    )
                }
            }
            .flowOn(Dispatchers.Default)

    private suspend inline fun <reified T> snapshot(
        session: Session,
        suffix: String,
        value: T,
    ): Snapshot {
        val encrypted =
            withContext(Dispatchers.Default) { cipher.encrypt(LorenzoJson.encodeToString(value)) }
        return Snapshot(session.key(suffix), encrypted, System.currentTimeMillis())
    }

    private suspend inline fun <reified T> cache(session: Session, suffix: String, value: T) {
        val row = snapshot(session, suffix, value)
        lock.withLock { if (sameSession(session)) dao.put(row) }
    }

    suspend fun login(token: String) {
        val me = LorenzoApi(apiUrl, token).me()
        val next = Session(token)
        val row = snapshot(next, "me", me)
        lock.withLock {
            cancelNotes()
            dao.clearNotes()
            dao.clearSnapshots()
            withContext(Dispatchers.IO) { secrets.save(token) }
            dao.put(row)
        }
    }

    suspend fun logout() = lock.withLock { clearSession() }

    private suspend fun clearSession() =
        withContext(NonCancellable) {
            cancelNotes()
            noteRevisions.clear()
            withContext(Dispatchers.IO) { secrets.clear() }
            dao.clearNotes()
            dao.clearSnapshots()
        }

    private suspend fun <T> authenticated(session: Session, block: suspend (LorenzoApi) -> T): T {
        lock.withLock { if (!sameSession(session)) throw CancellationException("Session changed") }
        try {
            return block(LorenzoApi(apiUrl, session.token))
        } catch (e: ApiException) {
            if (e.status == 401) lock.withLock { if (sameSession(session)) clearSession() }
            throw e
        }
    }

    suspend fun refreshMe(): Me {
        val session = session()
        val fresh = authenticated(session) { it.me() }
        val row = snapshot(session, "me", fresh)
        lock.withLock {
            if (sameSession(session)) {
                val old =
                    dao.snapshot(session.key("me"))?.let {
                        LorenzoJson.decodeFromString<Me>(cipher.decrypt(it.encrypted))
                    }
                if (
                    old != null &&
                        old.characters().map { it.key }.toSet() !=
                            fresh.characters().map { it.key }.toSet()
                ) {
                    dao.clearSnapshots()
                    val allowed = fresh.characters().map { it.key }.toSet()
                    dao.pending().forEach { pending ->
                        if (
                            LorenzoJson.decodeFromString<NoteDraft>(
                                    cipher.decrypt(pending.encrypted)
                                )
                                .character
                                .key !in allowed
                        )
                            dao.removeNote(pending.id)
                    }
                }
                dao.put(row)
            }
        }
        return fresh
    }

    suspend fun refreshInventory(character: Character) {
        val session = session()
        try {
            cache(
                session,
                "inventory/${character.key}",
                authenticated(session) { it.inventory(character) },
            )
        } catch (e: ApiException) {
            if (e.status in listOf(403, 404))
                lock.withLock { if (sameSession(session)) dao.clearSnapshots() }
            throw e
        }
    }

    suspend fun refreshNotes(character: Character, itemId: String) {
        val session = session()
        val suffix = notesKey(character, itemId)
        val revision = noteRevision(session, suffix)
        try {
            val fresh = authenticated(session) { it.notes(character.tenantId, itemId) }
            val row = snapshot(session, suffix, fresh)
            lock.withLock {
                if (sameSession(session) && noteRevisions[session.key(suffix)] == revision)
                    dao.put(row)
            }
        } catch (e: ApiException) {
            if (e.status in listOf(403, 404))
                lock.withLock {
                    if (sameSession(session)) dao.remove(session.key(notesKey(character, itemId)))
                }
            throw e
        }
    }

    suspend fun queueNote(
        character: Character,
        itemId: String,
        text: String,
        public: Boolean,
        locale: String,
    ) {
        require(text.isNotBlank())
        val session = session()
        val request =
            NoteCreate(
                UUID.randomUUID().toString(),
                isPublic = public,
                content = text.trim(),
                locale = locale,
            )
        val encrypted =
            withContext(Dispatchers.Default) {
                cipher.encrypt(LorenzoJson.encodeToString(NoteDraft(character, itemId, request)))
            }
        lock.withLock {
            check(sameSession(session))
            dao.putNote(PendingNote(request.id, encrypted))
            scheduleNotes()
        }
    }

    suspend fun retryNote(id: String) =
        lock.withLock {
            dao.pending().firstOrNull { it.id == id }?.let { dao.putNote(it.copy(error = null)) }
            scheduleNotes()
        }

    /**
     * A stable UUID makes POST replay safe (ADR 0222). Reader PUT is idempotent. Until both writes
     * and a readback succeed, the UI shows Pending.
     */
    suspend fun syncNotes(): Boolean =
        syncLock.withLock {
            val session = lock.withLock { currentSession() } ?: return@withLock true
            val rows = lock.withLock { if (sameSession(session)) dao.pending() else emptyList() }
            var retry = false
            for (row in rows.filter { it.error == null }) {
                try {
                    val draft =
                        LorenzoJson.decodeFromString<NoteDraft>(cipher.decrypt(row.encrypted))
                    val notes =
                        authenticated(session) { client ->
                            client.createNote(draft.character.tenantId, draft.itemId, draft.request)
                            if (!draft.request.isPublic)
                                client.addReader(
                                    draft.character.tenantId,
                                    row.id,
                                    draft.character.entityId,
                                )
                            client.notes(draft.character.tenantId, draft.itemId)
                        }
                    val suffix = notesKey(draft.character, draft.itemId)
                    val revision = noteRevision(session, suffix)
                    val snapshot = snapshot(session, suffix, notes)
                    lock.withLock {
                        if (sameSession(session)) {
                            if (noteRevisions[session.key(suffix)] == revision) dao.put(snapshot)
                            dao.removeNote(row.id)
                        }
                    }
                } catch (e: CancellationException) {
                    throw e
                } catch (e: ApiException) {
                    if (e.status == 401) return@withLock true
                    if (e.status >= 500 || e.status == 429) retry = true
                    else
                        lock.withLock {
                            if (sameSession(session))
                                dao.putNote(
                                    row.copy(
                                        error =
                                            "The server refused this note (${e.status}). Check access, then retry."
                                    )
                                )
                        }
                } catch (e: IOException) {
                    retry = true
                } catch (_: Exception) {
                    lock.withLock {
                        if (sameSession(session))
                            dao.putNote(
                                row.copy(
                                    error =
                                        "Couldn't confirm this note. Your draft is retained; try again."
                                )
                            )
                    }
                }
            }
            !retry
        }
}
