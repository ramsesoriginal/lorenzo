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
data class NoteDraft(
    val character: Character,
    val itemId: String,
    val request: NoteCreate,
    val bundle: InformationDraft? = null,
)

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
    private val composerLock = Mutex()
    private val noteRevisions = mutableMapOf<String, Long>()
    private var pictureEpoch = 0L
    private val invalidatedPictures = mutableSetOf<String>()

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
            dao.clearDrafts()
            dao.clearMedia()
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
            pictureEpoch++
            invalidatedPictures.clear()
            withContext(Dispatchers.IO) { secrets.clear() }
            dao.clearNotes()
            dao.clearDrafts()
            dao.clearMedia()
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
                    pictureEpoch++
                    dao.removeMediaScope(session.key("pictures/"))
                    val allowed = fresh.characters().map { it.key }.toSet()
                    val removedDraftKeys = mutableSetOf<String>()
                    dao.drafts(session.key("drafts"))
                        .filter { it.id.startsWith("composer/") }
                        .forEach { row ->
                            val draft =
                                LorenzoJson.decodeFromString<InformationDraft>(
                                    cipher.decrypt(row.encrypted)
                                )
                            if (draft.character.key !in allowed) {
                                removedDraftKeys += row.id
                                draft.parts
                                    .mapNotNull { it.mediaId }
                                    .forEach { dao.removeMedia(session.key("staged"), it) }
                                dao.removeDraft(row.scope, row.id)
                            }
                        }
                    dao.draft(session.key("drafts"), "capture")?.let { row ->
                        val capture =
                            LorenzoJson.decodeFromString<CaptureBinding>(
                                cipher.decrypt(row.encrypted)
                            )
                        if (capture.composerKey in removedDraftKeys)
                            dao.removeDraft(row.scope, row.id)
                    }
                    dao.pending().forEach { pending ->
                        if (
                            LorenzoJson.decodeFromString<NoteDraft>(
                                    cipher.decrypt(pending.encrypted)
                                )
                                .character
                                .key !in allowed
                        ) {
                            LorenzoJson.decodeFromString<NoteDraft>(
                                    cipher.decrypt(pending.encrypted)
                                )
                                .bundle
                                ?.parts
                                ?.mapNotNull { it.mediaId }
                                ?.forEach { dao.removeMedia(session.key("staged"), it) }
                            dao.removeNote(pending.id)
                        }
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
                lock.withLock {
                    if (sameSession(session)) {
                        dao.clearSnapshots()
                        pictureEpoch++
                        dao.removeMediaScope(session.key("pictures/"))
                    }
                }
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
                if (sameSession(session) && noteRevisions[session.key(suffix)] == revision) {
                    val old =
                        dao.snapshot(session.key(suffix))
                            ?.let {
                                LorenzoJson.decodeFromString<List<Information>>(
                                    cipher.decrypt(it.encrypted)
                                )
                            }
                            .orEmpty()
                    val visible =
                        fresh
                            .flatMap { it.payloads }
                            .filter { it.kind == "picture" }
                            .map { it.id }
                            .toSet()
                    invalidatedPictures.removeAll(visible)
                    old.flatMap { it.payloads }
                        .filter { it.kind == "picture" && it.id !in visible }
                        .forEach { payload ->
                            invalidatedPictures += payload.id
                            dao.removeMedia(
                                session.key("pictures/${character.tenantId}/"),
                                pictureKey(character.tenantId, payload),
                            )
                        }
                    dao.put(row)
                }
            }
        } catch (e: ApiException) {
            if (e.status in listOf(403, 404))
                lock.withLock {
                    if (sameSession(session)) {
                        dao.remove(session.key(notesKey(character, itemId)))
                        pictureEpoch++
                        dao.removeMediaScope(session.key("pictures/"))
                    }
                }
            throw e
        }
    }

    private fun composerKey(character: Character, itemId: String) =
        "composer/${character.key}/$itemId"

    fun observeComposer(character: Character, itemId: String) =
        dao.observeDraft(key("drafts"), composerKey(character, itemId))
            .map { row ->
                row?.let {
                    LorenzoJson.decodeFromString<InformationDraft>(cipher.decrypt(it.encrypted))
                }
            }
            .flowOn(Dispatchers.Default)

    private fun stored(session: Session, id: String, value: InformationDraft) =
        StoredDraft(session.key("drafts"), id, cipher.encrypt(LorenzoJson.encodeToString(value)))

    private suspend fun loadDraft(session: Session, id: String): InformationDraft? =
        dao.draft(session.key("drafts"), id)?.let {
            LorenzoJson.decodeFromString<InformationDraft>(cipher.decrypt(it.encrypted))
        }

    suspend fun startComposer(character: Character, itemId: String, locale: String) =
        composerLock.withLock {
            val session = session()
            val id = composerKey(character, itemId)
            lock.withLock {
                check(sameSession(session))
                if (loadDraft(session, id) == null)
                    dao.putDraft(
                        stored(
                            session,
                            id,
                            InformationDraft(
                                character = character,
                                itemId = itemId,
                                locale = locale,
                            ),
                        )
                    )
            }
        }

    suspend fun changeComposer(
        character: Character,
        itemId: String,
        change: (InformationDraft) -> InformationDraft,
    ) =
        composerLock.withLock {
            val session = session()
            lock.withLock {
                check(sameSession(session))
                val id = composerKey(character, itemId)
                loadDraft(session, id)?.let { old ->
                    val next = change(old)
                    require(
                        next.id == old.id &&
                            next.character == old.character &&
                            next.itemId == old.itemId
                    )
                    dao.putDraft(stored(session, id, next))
                    (old.parts.mapNotNull { it.mediaId } -
                            next.parts.mapNotNull { it.mediaId }.toSet())
                        .forEach { dao.removeMedia(session.key("staged"), it) }
                }
            }
        }

    suspend fun discardComposer(character: Character, itemId: String) =
        composerLock.withLock {
            val session = session()
            lock.withLock {
                check(sameSession(session))
                val id = composerKey(character, itemId)
                loadDraft(session, id)
                    ?.parts
                    ?.mapNotNull { it.mediaId }
                    ?.forEach { dao.removeMedia(session.key("staged"), it) }
                dao.removeDraft(session.key("drafts"), id)
                dao.removeDraft(session.key("drafts"), "capture")
            }
        }

    suspend fun beginCapture(
        character: Character,
        itemId: String,
        camera: Boolean,
    ): CaptureBinding =
        composerLock.withLock {
            val session = session()
            lock.withLock {
                check(sameSession(session))
                val key = composerKey(character, itemId)
                val draft = requireNotNull(loadDraft(session, key))
                check(dao.draft(session.key("drafts"), "capture") == null) {
                    "A picture selection is already open"
                }
                val binding = CaptureBinding(draftId = draft.id, composerKey = key, camera = camera)
                dao.putDraft(
                    StoredDraft(
                        session.key("drafts"),
                        "capture",
                        cipher.encrypt(LorenzoJson.encodeToString(binding)),
                    )
                )
                binding
            }
        }

    fun observeCapture() =
        dao.observeDraft(key("drafts"), "capture")
            .map { row ->
                row?.let {
                    LorenzoJson.decodeFromString<CaptureBinding>(cipher.decrypt(it.encrypted))
                }
            }
            .flowOn(Dispatchers.Default)

    suspend fun capture(): CaptureBinding? {
        val session = session()
        return lock.withLock {
            if (!sameSession(session)) null
            else
                dao.draft(session.key("drafts"), "capture")?.let {
                    LorenzoJson.decodeFromString<CaptureBinding>(cipher.decrypt(it.encrypted))
                }
        }
    }

    suspend fun markCaptureLaunched(id: String): CaptureBinding? {
        val session = session()
        return lock.withLock {
            if (!sameSession(session)) return@withLock null
            val row = dao.draft(session.key("drafts"), "capture") ?: return@withLock null
            val binding =
                LorenzoJson.decodeFromString<CaptureBinding>(cipher.decrypt(row.encrypted))
            if (binding.id != id || binding.launched) return@withLock null
            val next = binding.copy(launched = true)
            dao.putDraft(row.copy(encrypted = cipher.encrypt(LorenzoJson.encodeToString(next))))
            next
        }
    }

    private suspend fun chunks(scope: String, id: String, bytes: ByteArray): List<MediaChunk> =
        withContext(Dispatchers.Default) {
            (bytes.indices step (64 * 1024)).mapIndexed { index, start ->
                val part = bytes.copyOfRange(start, minOf(start + 64 * 1024, bytes.size))
                MediaChunk(
                    scope,
                    id,
                    index,
                    cipher.encrypt(java.util.Base64.getEncoder().encodeToString(part)),
                )
            }
        }

    private suspend fun bytes(scope: String, id: String): ByteArray? =
        withContext(Dispatchers.Default) {
            val rows = dao.media(scope, id)
            if (rows.isEmpty()) null
            else
                java.io.ByteArrayOutputStream().use { output ->
                    rows.forEachIndexed { index, row ->
                        check(row.part == index) { "Incomplete picture" }
                        output.write(
                            java.util.Base64.getDecoder().decode(cipher.decrypt(row.encrypted))
                        )
                    }
                    output.toByteArray()
                }
        }

    suspend fun finishCapture(binding: CaptureBinding, picture: ByteArray?) =
        composerLock.withLock {
            val session = session()
            val mediaId = UUID.randomUUID().toString()
            val rows = picture?.let { chunks(session.key("staged"), mediaId, it) }.orEmpty()
            lock.withLock {
                if (!sameSession(session)) return@withLock
                val current =
                    dao.draft(session.key("drafts"), "capture")?.let {
                        LorenzoJson.decodeFromString<CaptureBinding>(cipher.decrypt(it.encrypted))
                    }
                if (current != binding) return@withLock
                val draft = loadDraft(session, binding.composerKey)
                if (draft?.id == binding.draftId && picture != null) {
                    require(picture.size <= 2 * 1024 * 1024)
                    dao.stage(
                        rows,
                        stored(
                            session,
                            binding.composerKey,
                            draft.copy(
                                parts = draft.parts + DraftPart(kind = "picture", mediaId = mediaId)
                            ),
                        ),
                    )
                }
                dao.removeDraft(session.key("drafts"), "capture")
            }
        }

    suspend fun stagedPicture(id: String): ByteArray? {
        val session = session()
        val value = bytes(session.key("staged"), id)
        lock.withLock { check(sameSession(session)) }
        return value
    }

    suspend fun recipients(character: Character): List<Recipient> {
        val session = session()
        try {
            val fresh = authenticated(session) { it.recipients(character.tenantId) }
            cache(session, "recipients/${character.tenantId}", fresh)
            return fresh
        } catch (e: IOException) {
            if (e is ApiException && e.status !in listOf(429, 500, 502, 503, 504)) throw e
            lock.withLock { check(sameSession(session)) }
            return dao.snapshot(session.key("recipients/${character.tenantId}"))
                ?.let {
                    LorenzoJson.decodeFromString<List<Recipient>>(cipher.decrypt(it.encrypted))
                }
                .orEmpty()
        }
    }

    suspend fun queueComposer(character: Character, itemId: String) =
        composerLock.withLock {
            val session = session()
            lock.withLock {
                check(sameSession(session))
                val key = composerKey(character, itemId)
                val draft = requireNotNull(loadDraft(session, key))
                require(draft.hasContent)
                check(dao.draft(session.key("drafts"), "capture") == null) {
                    "Finish selecting the picture first"
                }
                val request =
                    NoteCreate(
                        draft.id,
                        content =
                            draft.parts.firstOrNull { it.kind == "description" }?.text.orEmpty(),
                        locale = draft.locale,
                    )
                dao.putNote(
                    PendingNote(
                        draft.id,
                        cipher.encrypt(
                            LorenzoJson.encodeToString(NoteDraft(character, itemId, request, draft))
                        ),
                    )
                )
                dao.removeDraft(session.key("drafts"), key)
                scheduleNotes()
            }
        }

    private fun pictureKey(tenantId: String, payload: Payload) =
        "pictures/$tenantId/${payload.id}/${payload.updatedAt}"

    suspend fun protectedPicture(tenantId: String, payload: Payload): ByteArray? {
        val session = session()
        val scope = session.key("pictures/$tenantId/")
        val id = pictureKey(tenantId, payload)
        val epoch =
            lock.withLock {
                check(sameSession(session))
                if (payload.id in invalidatedPictures) throw IOException("Picture access changed")
                pictureEpoch
            }
        try {
            val fresh = authenticated(session) { it.picture(tenantId, payload.id) }
            val rows = chunks(scope, id, fresh.bytes)
            lock.withLock {
                if (
                    sameSession(session) &&
                        pictureEpoch == epoch &&
                        payload.id !in invalidatedPictures
                )
                    dao.putMedia(rows)
                else throw CancellationException("Picture access changed")
            }
            return fresh.bytes
        } catch (e: IOException) {
            if (e is ApiException && e.status in listOf(401, 403, 404)) {
                lock.withLock {
                    if (sameSession(session)) {
                        invalidatedPictures += payload.id
                        dao.removeMedia(scope, id)
                    }
                }
                throw e
            }
            val cached = bytes(scope, id)
            lock.withLock {
                check(
                    sameSession(session) &&
                        pictureEpoch == epoch &&
                        payload.id !in invalidatedPictures
                )
            }
            return cached ?: throw e
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

    private suspend fun syncBundle(
        session: Session,
        client: LorenzoApi,
        row: PendingNote,
        original: NoteDraft,
    ) {
        var draft = requireNotNull(original.bundle)
        val tenant = draft.character.tenantId
        suspend fun progress(next: InformationDraft) {
            val encrypted =
                withContext(Dispatchers.Default) {
                    cipher.encrypt(LorenzoJson.encodeToString(original.copy(bundle = next)))
                }
            lock.withLock {
                check(sameSession(session))
                check(dao.pending().any { it.id == row.id })
                dao.putNote(row.copy(encrypted = encrypted))
            }
            draft = next
        }
        var current =
            try {
                client.editor(tenant, draft.id)
            } catch (e: ApiException) {
                if (e.status != 404 || draft.firstPayloadId != null) throw e
                client.createNote(tenant, draft.itemId, original.request.copy(isPublic = false))
                client.editor(tenant, draft.id)
            }
        val first = draft.parts.firstOrNull { it.kind == "description" }
        if (draft.firstPayloadId == null) {
            val initial = current.value.payloads.firstOrNull { it.kind == "description" }
            check(
                initial != null &&
                    initial.content == first?.text.orEmpty() &&
                    initial.locale == draft.locale
            ) {
                "Initial text changed"
            }
            progress(draft.copy(firstPayloadId = initial.id))
        }
        fun serverId(part: DraftPart) =
            if (part.id == first?.id) requireNotNull(draft.firstPayloadId) else part.id
        fun validate(value: Information, complete: Boolean) {
            val expected = draft.parts.associateBy(::serverId)
            val allowed = expected.keys + requireNotNull(draft.firstPayloadId)
            check(value.payloads.all { it.id in allowed }) {
                "Another payload was added; the draft is retained"
            }
            for (part in draft.parts) {
                val present = value.payloads.firstOrNull { it.id == serverId(part) }
                if (complete) check(present != null) { "The complete note was not returned" }
                if (present != null) {
                    check(present.kind == part.kind) { "Payload kind changed" }
                    if (part.kind == "description")
                        check(present.content == part.text && present.locale == draft.locale) {
                            "Text changed elsewhere"
                        }
                }
            }
            if (first == null)
                value.payloads
                    .firstOrNull { it.id == draft.firstPayloadId }
                    ?.let {
                        check(it.kind == "description" && it.content.orEmpty().isEmpty()) {
                            "Initial text changed"
                        }
                    }
        }
        validate(current.value, false)
        for (part in draft.parts) {
            val id = serverId(part)
            when (part.kind) {
                "picture" ->
                    client.appendPicture(
                        tenant,
                        draft.id,
                        id,
                        requireNotNull(bytes(session.key("staged"), requireNotNull(part.mediaId))),
                        current.etag,
                    )
                "description" ->
                    if (current.value.payloads.none { it.id == id })
                        client.appendText(
                            tenant,
                            draft.id,
                            TextAppend(id, part.text, draft.locale),
                            current.etag,
                        )
                else -> error("Unsupported draft payload")
            }
            current = client.editor(tenant, draft.id)
            validate(current.value, false)
        }
        if (first == null) {
            current.value.payloads
                .firstOrNull { it.id == draft.firstPayloadId }
                ?.let {
                    client.removePayload(tenant, it.id, "W/\"${it.updatedAt}\"")
                    current = client.editor(tenant, draft.id)
                }
        }
        val wanted = draft.parts.map(::serverId)
        val actual = current.value.payloads.map { it.id }
        if (draft.orderBase == null) {
            val appendedOrder =
                (listOfNotNull(if (first != null) draft.firstPayloadId else null) +
                    draft.parts.filter { it.id != first?.id }.map(::serverId))
            progress(draft.copy(orderBase = appendedOrder))
        }
        if (actual != wanted) {
            check(actual == draft.orderBase) { "Payload order changed elsewhere" }
            client.order(tenant, draft.id, wanted, current.etag)
        }
        val readers = client.audience(tenant, draft.id)
        val desired = draft.audience.normalized()
        if (readers.value.normalized() != desired) {
            check(readers.value.normalized() == Audience()) { "Readers changed elsewhere" }
            client.setAudience(tenant, draft.id, desired, readers.etag)
        }
        val confirmed = client.editor(tenant, draft.id).value
        validate(confirmed, true)
        check(confirmed.payloads.map { it.id } == wanted) { "Payload order was not confirmed" }
        check(client.audience(tenant, draft.id).value.normalized() == desired) {
            "Readers were not confirmed"
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
                    val suffix = notesKey(draft.character, draft.itemId)
                    val revision = noteRevision(session, suffix)
                    val notes =
                        authenticated(session) { client ->
                            if (draft.bundle != null) {
                                syncBundle(session, client, row, draft)
                            } else {
                                client.createNote(
                                    draft.character.tenantId,
                                    draft.itemId,
                                    draft.request,
                                )
                                if (!draft.request.isPublic)
                                    client.addReader(
                                        draft.character.tenantId,
                                        row.id,
                                        draft.character.entityId,
                                    )
                            }
                            client.notes(draft.character.tenantId, draft.itemId)
                        }
                    val snapshot = snapshot(session, suffix, notes)
                    val visible = notes.firstOrNull { it.id == row.id }
                    val pictureRows = mutableListOf<MediaChunk>()
                    if (visible != null)
                        for (part in
                            draft.bundle?.parts.orEmpty().filter { it.kind == "picture" }) {
                            val payload =
                                visible.payloads.firstOrNull {
                                    it.id == part.id && it.kind == "picture"
                                } ?: continue
                            val data =
                                bytes(session.key("staged"), requireNotNull(part.mediaId))
                                    ?: continue
                            pictureRows +=
                                chunks(
                                    session.key("pictures/${draft.character.tenantId}/"),
                                    pictureKey(draft.character.tenantId, payload),
                                    data,
                                )
                        }
                    lock.withLock {
                        if (sameSession(session)) {
                            if (noteRevisions[session.key(suffix)] == revision) {
                                dao.put(snapshot)
                                dao.putMedia(pictureRows)
                            }
                            dao.removeNote(row.id)
                            draft.bundle
                                ?.parts
                                ?.mapNotNull { it.mediaId }
                                ?.forEach { dao.removeMedia(session.key("staged"), it) }
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
                                    (dao.pending().firstOrNull { it.id == row.id } ?: row).copy(
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
                                (dao.pending().firstOrNull { it.id == row.id } ?: row).copy(
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
