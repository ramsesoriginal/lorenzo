package io.lorenzo.inventory.ui

import android.os.SystemClock
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import io.lorenzo.inventory.BuildConfig
import io.lorenzo.inventory.core.*
import io.lorenzo.inventory.data.*
import java.io.IOException
import java.util.Locale
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*

data class UiState(
    val signedIn: Boolean = false,
    val characters: List<Character> = emptyList(),
    val character: Character? = null,
    val inventory: Inventory? = null,
    val item: Item? = null,
    val notes: List<Information> = emptyList(),
    val queued: List<QueuedNote> = emptyList(),
    val composer: InformationDraft? = null,
    val capture: CaptureBinding? = null,
    val recipients: List<Recipient> = emptyList(),
    val updatedAt: Long? = null,
    val busy: Boolean = false,
    val submitting: Boolean = false,
    val error: String? = null,
    val device: DeviceCode? = null,
    val locales: List<String> = listOf(Locale.getDefault().toLanguageTag()),
)

class InventoryViewModel(
    private val repository: InventoryRepository,
    private val secrets: SecretStore,
    private val saved: SavedStateHandle,
) : ViewModel() {
    private val mutable = MutableStateFlow(UiState())
    val state = mutable.asStateFlow()
    private var sessionJob: Job? = null
    private var inventoryJob: Job? = null
    private var noteJob: Job? = null
    private var refreshJob: Job? = null
    private var refreshGeneration = 0L
    private var deviceJob: Job? = null

    init {
        viewModelScope.launch {
            secrets.token.collectLatest { token ->
                sessionJob?.cancelAndJoin()
                inventoryJob?.cancelAndJoin()
                noteJob?.cancelAndJoin()
                refreshJob?.cancelAndJoin()
                mutable.value = UiState(signedIn = token != null)
                if (token != null) {
                    sessionJob = launch {
                        launch {
                            repository.observeCapture().collect { capture ->
                                mutable.update { it.copy(capture = capture) }
                            }
                        }
                        launch {
                            repository.observeMe().collect { cached ->
                                mutable.update {
                                    it.copy(
                                        characters = cached?.value?.characters().orEmpty(),
                                        locales =
                                            cached?.value?.locales?.ifEmpty { it.locales }
                                                ?: it.locales,
                                    )
                                }
                                if (cached != null && mutable.value.character == null) {
                                    val selected = saved.get<String>("character")
                                    cached.value
                                        .characters()
                                        .firstOrNull { it.key == selected }
                                        ?.let(::select)
                                }
                            }
                        }
                        launch {
                            repository.observeQueue().collect { queue ->
                                mutable.update { it.copy(queued = queue) }
                            }
                        }
                    }
                    refresh()
                }
            }
        }
    }

    private suspend fun attempt(block: suspend () -> Unit) {
        try {
            block()
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            mutable.update {
                it.copy(
                    error =
                        when (e) {
                            is PictureImportException -> e.message.orEmpty()
                            is ApiException ->
                                when (e.status) {
                                    401 -> "Your sign-in expired or was revoked. Connect again."
                                    403,
                                    404 -> "You no longer have access. Refresh your characters."
                                    else -> e.problem.title
                                }
                            is IOException ->
                                "Couldn't connect. Downloaded data is still available."
                            else -> "Couldn't complete this action. Please try again."
                        }
                )
            }
        }
    }

    fun login(token: String) {
        if (mutable.value.busy) return
        deviceJob?.cancel()
        viewModelScope.launch {
            mutable.update { it.copy(busy = true, error = null) }
            try {
                attempt { repository.login(token.trim()) }
            } finally {
                mutable.update { it.copy(busy = false) }
            }
        }
    }

    fun connectDevice() {
        deviceJob?.cancel()
        deviceJob =
            viewModelScope.launch {
                mutable.update { it.copy(busy = true, error = null) }
                try {
                    attempt {
                        val api = LorenzoApi(BuildConfig.API_BASE_URL)
                        val device = api.beginDeviceLogin()
                        mutable.update { it.copy(device = device) }
                        var interval = device.interval.coerceAtLeast(1).toLong()
                        val deadline = SystemClock.elapsedRealtime() + device.expiresIn * 1000L
                        while (SystemClock.elapsedRealtime() < deadline) {
                            delay(interval * 1000)
                            if (SystemClock.elapsedRealtime() >= deadline) break
                            try {
                                repository.login(api.pollDevice(device.deviceCode).token)
                                return@attempt
                            } catch (e: ApiException) {
                                when (e.problem.type.substringAfterLast('/')) {
                                    "authorization-pending" -> Unit
                                    "slow-down" -> interval += 5
                                    else -> throw e
                                }
                            } catch (e: IOException) {
                                interval = (interval * 2).coerceAtMost(30)
                            }
                        }
                        mutable.update {
                            it.copy(error = "This connection code expired. Start again.")
                        }
                    }
                } finally {
                    mutable.update {
                        it.copy(busy = if (it.signedIn) it.busy else false, device = null)
                    }
                }
            }
    }

    fun cancelDevice() {
        deviceJob?.cancel()
        mutable.update { it.copy(device = null, busy = false) }
    }

    fun select(character: Character) {
        inventoryJob?.cancel()
        noteJob?.cancel()
        refreshJob?.cancel()
        val restoring = saved.get<String>("character") == character.key
        val restoreItem = if (restoring) saved.get<String>("item") else null
        if (!restoring) saved["item"] = null
        saved["character"] = character.key
        mutable.update {
            it.copy(
                character = character,
                inventory = null,
                item = null,
                notes = emptyList(),
                updatedAt = null,
                error = null,
            )
        }
        inventoryJob =
            viewModelScope.launch {
                var restoredItem = false
                repository.observeInventory(character).collect { cached ->
                    mutable.update { current ->
                        current.copy(
                            inventory = cached?.value,
                            updatedAt = cached?.updatedAt,
                            item =
                                current.item?.let { selected ->
                                    cached?.value?.items?.find { it.entityId == selected.entityId }
                                },
                        )
                    }
                    if (!restoredItem && cached != null) {
                        restoredItem = true
                        cached.value.items.find { it.entityId == restoreItem }?.let(::open)
                    }
                }
            }
        refresh()
    }

    fun open(item: Item) {
        val character = mutable.value.character ?: return
        noteJob?.cancel()
        saved["item"] = item.entityId
        mutable.update {
            it.copy(
                item = item,
                notes = emptyList(),
                composer = null,
                recipients = emptyList(),
                error = null,
            )
        }
        noteJob =
            viewModelScope.launch {
                launch {
                    repository.observeComposer(character, item.entityId).collect { draft ->
                        mutable.update { it.copy(composer = draft) }
                    }
                }
                launch {
                    attempt {
                        val readers = repository.recipients(character)
                        mutable.update { it.copy(recipients = readers) }
                    }
                }
                launch {
                    repository.observeNotes(character, item.entityId).collect { cached ->
                        mutable.update { it.copy(notes = cached?.value.orEmpty()) }
                    }
                }
                attempt { repository.refreshNotes(character, item.entityId) }
            }
    }

    fun back() {
        if (mutable.value.item != null) {
            noteJob?.cancel()
            saved["item"] = null
            mutable.update { it.copy(item = null, notes = emptyList(), error = null) }
        } else if (mutable.value.character != null) {
            inventoryJob?.cancel()
            refreshJob?.cancel()
            saved["character"] = null
            mutable.update {
                it.copy(
                    character = null,
                    inventory = null,
                    updatedAt = null,
                    busy = false,
                    error = null,
                )
            }
        }
    }

    fun refresh() {
        val generation = ++refreshGeneration
        refreshJob?.cancel()
        refreshJob =
            viewModelScope.launch {
                mutable.update { it.copy(busy = true, error = null) }
                try {
                    attempt {
                        val refreshed = repository.refreshMe()
                        val character = mutable.value.character
                        if (character != null) {
                            if (refreshed.characters().none { it.key == character.key }) {
                                back()
                                return@attempt
                            }
                            repository.refreshInventory(character)
                            mutable.value.item?.let {
                                repository.refreshNotes(character, it.entityId)
                            }
                        } else {
                            // Inventory responses already contain descriptions and stats: warm
                            // three
                            // likely selections without flooding the API or downloading every
                            // library.
                            refreshed.characters().take(3).forEach { c ->
                                try {
                                    repository.refreshInventory(c)
                                } catch (e: CancellationException) {
                                    throw e
                                } catch (_: IOException) {
                                    /* A failed prefetch never hides the roster. */
                                }
                            }
                        }
                    }
                } finally {
                    if (generation == refreshGeneration) mutable.update { it.copy(busy = false) }
                }
            }
    }

    fun startNote() {
        val snapshot = mutable.value
        val character = snapshot.character ?: return
        val item = snapshot.item ?: return
        viewModelScope.launch {
            attempt {
                repository.startComposer(
                    character,
                    item.entityId,
                    snapshot.locales.firstOrNull() ?: "en-US",
                )
            }
        }
    }

    fun changeNote(change: (InformationDraft) -> InformationDraft) {
        val snapshot = mutable.value
        val character = snapshot.character ?: return
        val item = snapshot.item ?: return
        viewModelScope.launch {
            attempt { repository.changeComposer(character, item.entityId, change) }
        }
    }

    fun discardNote() {
        val snapshot = mutable.value
        val character = snapshot.character ?: return
        val item = snapshot.item ?: return
        viewModelScope.launch { attempt { repository.discardComposer(character, item.entityId) } }
    }

    fun queueNote(onQueued: () -> Unit) {
        val snapshot = mutable.value
        val character = snapshot.character ?: return
        val item = snapshot.item ?: return
        if (snapshot.submitting) return
        viewModelScope.launch {
            mutable.update { it.copy(submitting = true) }
            try {
                attempt {
                    repository.queueComposer(character, item.entityId)
                    onQueued()
                }
            } finally {
                mutable.update { it.copy(submitting = false) }
            }
        }
    }

    fun preparePicture(camera: Boolean) {
        val snapshot = mutable.value
        val character = snapshot.character ?: return
        val item = snapshot.item ?: return
        viewModelScope.launch {
            attempt { repository.beginCapture(character, item.entityId, camera) }
        }
    }

    fun launchPicture(
        context: android.content.Context,
        id: String,
        launch: (android.net.Uri?) -> Unit,
    ) {
        viewModelScope.launch {
            attempt {
                val binding = repository.markCaptureLaunched(id) ?: return@attempt
                try {
                    val uri =
                        withContext(Dispatchers.IO) {
                            if (binding.camera) NotePictures.captureUri(context, binding.id)
                            else null
                        }
                    check(repository.capture()?.id == binding.id) {
                        "Picture selection was cancelled"
                    }
                    launch(uri)
                } catch (e: Exception) {
                    withContext(NonCancellable) {
                        runCatching { repository.finishCapture(binding, null) }
                        withContext(Dispatchers.IO) {
                            NotePictures.removeCapture(context, binding.id)
                        }
                    }
                    throw e
                }
            }
        }
    }

    fun receivePicture(
        context: android.content.Context,
        uri: android.net.Uri?,
        camera: Boolean,
        accepted: Boolean = true,
        expectedId: String,
    ) {
        viewModelScope.launch {
            attempt {
                val binding = repository.capture() ?: return@attempt
                if (binding.camera != camera || binding.id != expectedId) return@attempt
                try {
                    val source =
                        if (!accepted) null
                        else if (camera) NotePictures.captureUri(context, binding.id) else uri
                    val bytes =
                        source?.let {
                            try {
                                NotePictures.normalize(context, it)
                            } catch (e: CancellationException) {
                                throw e
                            } catch (_: Exception) {
                                throw PictureImportException()
                            }
                        }
                    repository.finishCapture(binding, bytes)
                } finally {
                    withContext(NonCancellable) {
                        runCatching { repository.finishCapture(binding, null) }
                        withContext(Dispatchers.IO) {
                            NotePictures.removeCapture(context, binding.id)
                        }
                    }
                }
            }
        }
    }

    fun cancelPicture(context: android.content.Context) {
        viewModelScope.launch {
            attempt {
                val binding = repository.capture() ?: return@attempt
                repository.finishCapture(binding, null)
                withContext(Dispatchers.IO) { NotePictures.removeCapture(context, binding.id) }
            }
        }
    }

    suspend fun picture(tenantId: String, payload: Payload) =
        repository.protectedPicture(tenantId, payload)

    suspend fun stagedPicture(id: String) = repository.stagedPicture(id)

    fun addNote(text: String, public: Boolean, onQueued: () -> Unit) {
        val snapshot = mutable.value
        val character = snapshot.character ?: return
        val item = snapshot.item ?: return
        if (snapshot.submitting) return
        viewModelScope.launch {
            mutable.update { it.copy(submitting = true) }
            try {
                attempt {
                    repository.queueNote(
                        character,
                        item.entityId,
                        text,
                        public,
                        snapshot.locales.firstOrNull() ?: "en-US",
                    )
                    onQueued()
                }
            } finally {
                mutable.update { it.copy(submitting = false) }
            }
        }
    }

    fun retryNote(id: String) {
        viewModelScope.launch { attempt { repository.retryNote(id) } }
    }

    fun logout() {
        viewModelScope.launch {
            inventoryJob?.cancelAndJoin()
            noteJob?.cancelAndJoin()
            refreshJob?.cancelAndJoin()
            attempt {
                repository.logout()
                saved["character"] = null
                saved["item"] = null
            }
        }
    }

    fun dismissError() {
        mutable.update { it.copy(error = null) }
    }
}
