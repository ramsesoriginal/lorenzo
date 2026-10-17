package io.lorenzo.inventory.ui

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.rememberTransformableState
import androidx.compose.foundation.gestures.transformable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import io.lorenzo.inventory.core.*
import io.lorenzo.inventory.data.*
import kotlinx.coroutines.CancellationException

/** Register both contracts outside the conditional editor so pending results survive recreation. */
@Composable
fun rememberNoteAcquisition(state: UiState, vm: InventoryViewModel): (Boolean) -> Unit {
    val context = LocalContext.current.applicationContext
    // Distinct registry keys keep a late, cancelled result from reaching a newer draft.
    state.capture?.let { binding ->
        key(binding.id) {
            val gallery =
                rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri
                    ->
                    vm.receivePicture(context, uri, false, expectedId = binding.id)
                }
            val camera =
                rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { success
                    ->
                    vm.receivePicture(context, null, true, success, expectedId = binding.id)
                }
            LaunchedEffect(binding.id) {
                if (!binding.launched)
                    vm.launchPicture(context, binding.id) { uri ->
                        if (binding.camera) camera.launch(requireNotNull(uri))
                        else
                            gallery.launch(
                                PickVisualMediaRequest(
                                    ActivityResultContracts.PickVisualMedia.ImageOnly
                                )
                            )
                    }
            }
        }
    }
    return vm::preparePicture
}

@Composable
fun InformationComposer(
    state: UiState,
    vm: InventoryViewModel,
    acquire: (Boolean) -> Unit,
    onQueued: () -> Unit,
) {
    val draft = state.composer ?: return
    val context = LocalContext.current.applicationContext
    var audienceOpen by remember(draft.id) { mutableStateOf(false) }
    var search by remember(draft.id) { mutableStateOf("") }
    Card {
        Column(
            Modifier.fillMaxWidth().padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            draft.parts.forEachIndexed { index, part ->
                key(part.id) {
                    if (part.kind == "description") {
                        var text by remember(part.id) { mutableStateOf(part.text) }
                        OutlinedTextField(
                            text,
                            { next ->
                                text = next
                                vm.changeNote { old ->
                                    old.copy(
                                        parts =
                                            old.parts.map {
                                                if (it.id == part.id) it.copy(text = next) else it
                                            }
                                    )
                                }
                            },
                            Modifier.fillMaxWidth(),
                            label = { Text("LorenzoScript text") },
                            minLines = 3,
                            enabled = !state.submitting,
                        )
                    } else
                        part.mediaId?.let { id ->
                            NotePicture("draft/$id") { vm.stagedPicture(id) }
                        }
                    if (draft.parts.size > 1 || part.kind != "description")
                        Row {
                            TextButton(
                                onClick = {
                                    vm.changeNote { old ->
                                        val parts = old.parts.toMutableList()
                                        val at = parts.indexOfFirst { it.id == part.id }
                                        if (at > 0) java.util.Collections.swap(parts, at, at - 1)
                                        old.copy(parts = parts)
                                    }
                                },
                                enabled = index > 0 && !state.submitting,
                            ) {
                                Text("Move up")
                            }
                            TextButton(
                                onClick = {
                                    vm.changeNote { old ->
                                        val parts = old.parts.toMutableList()
                                        val at = parts.indexOfFirst { it.id == part.id }
                                        if (at >= 0 && at < parts.lastIndex)
                                            java.util.Collections.swap(parts, at, at + 1)
                                        old.copy(parts = parts)
                                    }
                                },
                                enabled = index < draft.parts.lastIndex && !state.submitting,
                            ) {
                                Text("Move down")
                            }
                            TextButton(
                                onClick = {
                                    vm.changeNote { old ->
                                        old.copy(parts = old.parts.filterNot { it.id == part.id })
                                    }
                                },
                                enabled = !state.submitting,
                            ) {
                                Text("Remove")
                            }
                        }
                }
            }
            Row {
                TextButton(
                    onClick = { vm.changeNote { it.copy(parts = it.parts + DraftPart()) } },
                    enabled = !state.submitting,
                ) {
                    Text("Add text")
                }
                TextButton(
                    onClick = { acquire(false) },
                    enabled = state.capture == null && !state.submitting,
                ) {
                    Text("Gallery")
                }
                TextButton(
                    onClick = { acquire(true) },
                    enabled = state.capture == null && !state.submitting,
                ) {
                    Text("Take photo")
                }
            }
            if (state.capture != null) {
                Text(
                    "A picture selection is in progress. It belongs to the note that opened it.",
                    style = MaterialTheme.typography.bodySmall,
                )
                TextButton(onClick = { vm.cancelPicture(context) }) {
                    Text("Cancel picture selection")
                }
            }
            TextButton(onClick = { audienceOpen = !audienceOpen }) { Text("Who can read this") }
            if (audienceOpen) {
                Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                    Checkbox(
                        draft.audience.isPublic,
                        { public ->
                            vm.changeNote {
                                it.copy(audience = it.audience.copy(isPublic = public))
                            }
                        },
                        enabled = !state.submitting,
                    )
                    Text("Everyone with access to this entry")
                }
                Text(
                    "Campaign GMs and library administrators retain their role access. Selected groups follow their current membership.",
                    style = MaterialTheme.typography.bodySmall,
                )
                OutlinedTextField(
                    search,
                    { search = it },
                    label = { Text("Find a character or group") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                )
                val choices =
                    (listOf(Recipient(draft.character.entityId, draft.character.name)) +
                            state.recipients)
                        .distinctBy { it.entityId }
                val missing =
                    draft.audience.entityIds
                        .filter { id -> choices.none { it.entityId == id } }
                        .map { Recipient(it, "Unavailable recipient") }
                Column(Modifier.heightIn(max = 240.dp).verticalScroll(rememberScrollState())) {
                    (choices + missing)
                        .filter { it.name.contains(search, true) }
                        .forEach { recipient ->
                            Row(
                                verticalAlignment = androidx.compose.ui.Alignment.CenterVertically
                            ) {
                                Checkbox(
                                    recipient.entityId in draft.audience.entityIds,
                                    { checked ->
                                        vm.changeNote { old ->
                                            old.copy(
                                                audience =
                                                    old.audience.copy(
                                                        entityIds =
                                                            if (checked)
                                                                (old.audience.entityIds +
                                                                        recipient.entityId)
                                                                    .distinct()
                                                            else
                                                                old.audience.entityIds -
                                                                    recipient.entityId
                                                    )
                                            )
                                        }
                                    },
                                    enabled = !state.submitting,
                                )
                                Text(recipient.name)
                            }
                        }
                }
                if (state.recipients.isEmpty())
                    Text(
                        "Only downloaded recipients are available offline. Existing selections are kept.",
                        style = MaterialTheme.typography.bodySmall,
                    )
            }
            Text(
                "Text and pictures share this audience. Your draft stays on this phone. Add note sends it when a connection is available.",
                style = MaterialTheme.typography.bodySmall,
            )
            Row {
                Button(
                    onClick = { vm.queueNote(onQueued) },
                    enabled = draft.hasContent && !state.submitting && state.capture == null,
                ) {
                    Text(if (state.submitting) "Keeping note…" else "Add note")
                }
                TextButton(
                    onClick = {
                        vm.discardNote()
                        onQueued()
                    },
                    enabled = !state.submitting && state.capture == null,
                ) {
                    Text("Discard draft")
                }
            }
        }
    }
}

@Composable
fun NotePicture(identity: String, load: suspend () -> ByteArray?) {
    data class Loaded(
        val bytes: ByteArray? = null,
        val bitmap: android.graphics.Bitmap? = null,
        val error: Boolean = false,
    )
    val loaded by
        produceState(Loaded(), identity) {
            value =
                try {
                    val bytes = load()
                    if (bytes == null) Loaded(error = true)
                    else Loaded(bytes, NotePictures.preview(bytes, 768))
                } catch (e: CancellationException) {
                    throw e
                } catch (_: Exception) {
                    Loaded(error = true)
                }
        }
    // Compose display lists may outlive composition; let the runtime release displayed bitmaps.
    var expanded by remember(identity) { mutableStateOf(false) }
    when {
        loaded.error ->
            Text(
                "Picture unavailable. Refresh when connected.",
                style = MaterialTheme.typography.bodySmall,
            )
        loaded.bitmap == null -> LinearProgressIndicator(Modifier.fillMaxWidth())
        else ->
            Image(
                requireNotNull(loaded.bitmap).asImageBitmap(),
                "Attached picture; tap to enlarge",
                Modifier.fillMaxWidth().heightIn(max = 320.dp).clickable { expanded = true },
            )
    }
    if (expanded)
        Dialog(
            onDismissRequest = { expanded = false },
            properties = DialogProperties(usePlatformDefaultWidth = false),
        ) {
            val large by
                produceState<android.graphics.Bitmap?>(null, identity) {
                    loaded.bytes?.let { value = NotePictures.preview(it, 2048) }
                }

            var scale by remember { mutableFloatStateOf(1f) }
            var offset by remember { mutableStateOf(androidx.compose.ui.geometry.Offset.Zero) }
            val transform = rememberTransformableState { zoom, pan, _ ->
                scale = (scale * zoom).coerceIn(1f, 5f)
                offset = if (scale == 1f) androidx.compose.ui.geometry.Offset.Zero else offset + pan
            }
            Surface(Modifier.fillMaxSize()) {
                Column {
                    TextButton(onClick = { expanded = false }) { Text("Close picture") }
                    large?.let {
                        Image(
                            it.asImageBitmap(),
                            "Attached picture",
                            Modifier.fillMaxSize()
                                .graphicsLayer(
                                    scaleX = scale,
                                    scaleY = scale,
                                    translationX = offset.x,
                                    translationY = offset.y,
                                )
                                .transformable(transform),
                        )
                    }
                }
            }
        }
}
