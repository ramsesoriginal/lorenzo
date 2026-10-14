package io.lorenzo.inventory.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import io.lorenzo.inventory.R
import io.lorenzo.inventory.core.*
import java.text.DateFormat
import java.util.Date

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun InventoryScreen(state: UiState, vm: InventoryViewModel) {
    var signOut by remember { mutableStateOf(false) }
    BackHandler(enabled = state.character != null) { vm.back() }
    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(10.dp),
                    ) {
                        if (state.character == null)
                            Icon(
                                painterResource(R.drawable.brand_mark),
                                null,
                                tint = androidx.compose.ui.graphics.Color.Unspecified,
                                modifier = Modifier.size(28.dp),
                            )
                        Text(
                            if (!state.signedIn) "Lorenzo"
                            else if (state.character == null) "Your characters"
                            else if (state.item != null) "Item" else state.character.name,
                            maxLines = 1,
                            overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis,
                        )
                    }
                },
                navigationIcon = {
                    if (state.character != null)
                        IconButton(onClick = vm::back) {
                            Icon(painterResource(R.drawable.ic_arrow_left), "Back")
                        }
                },
                actions = {
                    if (state.signedIn) {
                        IconButton(onClick = vm::refresh, enabled = !state.busy) {
                            Icon(painterResource(R.drawable.ic_refresh), "Refresh")
                        }
                        IconButton(onClick = { signOut = true }) {
                            Icon(painterResource(R.drawable.ic_logout), "Sign out")
                        }
                    }
                },
            )
        }
    ) { insets ->
        Column(Modifier.fillMaxSize().padding(insets).consumeWindowInsets(insets)) {
            if (state.error != null)
                Surface(color = MaterialTheme.colorScheme.errorContainer) {
                    Row(
                        Modifier.fillMaxWidth().padding(start = 16.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            state.error,
                            Modifier.weight(1f),
                            style = MaterialTheme.typography.bodyMedium,
                        )
                        TextButton(onClick = vm::dismissError) { Text("Dismiss") }
                    }
                }
            if (!state.signedIn) LoginScreen(state, vm)
            else {
                if (state.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
                PullToRefreshBox(
                    isRefreshing = state.busy,
                    onRefresh = vm::refresh,
                    modifier = Modifier.weight(1f),
                ) {
                    when {
                        state.item != null -> ItemScreen(state, vm)
                        state.character != null -> InventoryList(state, vm)
                        else -> CharacterList(state, vm)
                    }
                }
            }
        }
    }
    if (signOut)
        AlertDialog(
            onDismissRequest = { signOut = false },
            title = { Text("Sign out of this device?") },
            text = {
                Text(
                    "Downloaded data and ${state.queued.size} pending notes will be removed. Your token remains active until revoked in account hub."
                )
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        signOut = false
                        vm.logout()
                    }
                ) {
                    Text("Sign out")
                }
            },
            dismissButton = { TextButton(onClick = { signOut = false }) { Text("Cancel") } },
        )
}

@Composable
private fun LoginScreen(state: UiState, vm: InventoryViewModel) {
    var token by remember { mutableStateOf("") } // Never place the secret in saved-state bundles.
    var paste by rememberSaveable { mutableStateOf(false) }
    val uri = LocalUriHandler.current
    LazyColumn(
        Modifier.fillMaxSize().imePadding(),
        contentPadding = PaddingValues(24.dp),
        verticalArrangement = Arrangement.spacedBy(20.dp),
    ) {
        item {
            Spacer(Modifier.height(36.dp))
            Text("Your gear.\nReady for the table.", style = MaterialTheme.typography.displaySmall)
        }
        item {
            Text(
                "Choose a character, find an item, and keep a note. Everything else stays read-only.",
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        item {
            Card {
                Column(
                    Modifier.fillMaxWidth().padding(20.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    val device = state.device
                    if (device != null) {
                        Text("Connect this phone", style = MaterialTheme.typography.titleLarge)
                        Text(device.userCode, style = MaterialTheme.typography.headlineMedium)
                        Text(
                            "Approve this code in account hub. We'll finish connecting automatically."
                        )
                        Button(
                            onClick = { uri.openUri(device.verificationUri) },
                            Modifier.fillMaxWidth(),
                        ) {
                            Text("Open account hub")
                        }
                        TextButton(onClick = vm::cancelDevice) { Text("Cancel") }
                    } else {
                        Text("Welcome to Lorenzo", style = MaterialTheme.typography.titleLarge)
                        Button(
                            onClick = vm::connectDevice,
                            enabled = !state.busy,
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text(if (state.busy) "Connecting…" else "Connect with account hub")
                        }
                        Text(
                            "Sign in through your browser and approve this device. No password is stored here.",
                            style = MaterialTheme.typography.bodyMedium,
                        )
                        TextButton(onClick = { paste = !paste }, enabled = !state.busy) {
                            Text("Use a personal access token")
                        }
                        if (paste) {
                            OutlinedTextField(
                                value = token,
                                onValueChange = { token = it },
                                label = { Text("Personal access token") },
                                visualTransformation = PasswordVisualTransformation(),
                                singleLine = true,
                                keyboardOptions =
                                    KeyboardOptions(keyboardType = KeyboardType.Password),
                                modifier = Modifier.fillMaxWidth(),
                            )
                            Button(
                                onClick = {
                                    vm.login(token)
                                    token = ""
                                },
                                enabled = token.startsWith("lor_pat_") && !state.busy,
                                modifier = Modifier.fillMaxWidth(),
                            ) {
                                Text("Sign in")
                            }
                        }
                    }
                }
            }
        }
        if (state.busy) item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
        item {
            Text(
                "Your sign-in and downloaded information are encrypted on this phone.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun CharacterList(state: UiState, vm: InventoryViewModel) {
    LazyColumn(
        Modifier.fillMaxSize(),
        contentPadding = PaddingValues(20.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Text("Take your world\nwith you.", style = MaterialTheme.typography.headlineLarge)
            Spacer(Modifier.height(8.dp))
            Text(
                "Characters you play, across your libraries.",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        if (state.characters.isEmpty() && !state.busy)
            item {
                Empty(
                    "No characters yet",
                    "Ask your GM to add you as a player of a character, then refresh.",
                )
            }
        items(state.characters, key = { it.key }) { character ->
            Card(onClick = { vm.select(character) }) {
                Row(
                    Modifier.fillMaxWidth().padding(20.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(16.dp),
                ) {
                    Icon(
                        painterResource(R.drawable.ic_user),
                        null,
                        tint = MaterialTheme.colorScheme.primary,
                    )
                    Column(Modifier.weight(1f)) {
                        Text(character.name, style = MaterialTheme.typography.titleLarge)
                        Text(
                            "Open inventory",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Icon(painterResource(R.drawable.ic_chevron_right), null)
                }
            }
        }
    }
}

@Composable
private fun InventoryList(state: UiState, vm: InventoryViewModel) {
    var query by rememberSaveable(state.character?.key) { mutableStateOf("") }
    val groups = state.inventory?.groups.orEmpty()
    LazyColumn(
        Modifier.fillMaxSize(),
        contentPadding = PaddingValues(20.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        item {
            Text("Inventory", style = MaterialTheme.typography.headlineLarge)
            Text(
                "${state.inventory?.items?.size ?: 0} items · read-only",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            state.updatedAt?.let {
                Text(
                    "Downloaded ${DateFormat.getDateTimeInstance(DateFormat.SHORT, DateFormat.SHORT).format(Date(it))}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Spacer(Modifier.height(16.dp))
            OutlinedTextField(
                query,
                { query = it },
                Modifier.fillMaxWidth(),
                placeholder = { Text("Find an item") },
                singleLine = true,
                leadingIcon = { Icon(painterResource(R.drawable.ic_search), null) },
            )
        }
        if (state.inventory == null && !state.busy)
            item {
                Empty(
                    "No downloaded inventory",
                    "Connect and refresh to download this character's gear.",
                )
            }
        if (state.inventory?.items?.isEmpty() == true)
            item { Empty("Traveling light", "This character isn't holding any items yet.") }
        var found = 0
        groups.forEach { group ->
            val visible =
                group.items.filter {
                    it.title.contains(query, ignoreCase = true) ||
                        it.tags.any { tag -> tag.value == true && tag.name.contains(query, true) }
                }
            found += visible.size
            if (visible.isNotEmpty()) {
                item(key = "group/${group.container.id}") {
                    Row(
                        Modifier.padding(top = 16.dp, bottom = 4.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Icon(
                            painterResource(R.drawable.ic_backpack),
                            null,
                            Modifier.size(20.dp),
                            tint = MaterialTheme.colorScheme.primary,
                        )
                        Text(
                            if (group.container.id == state.character?.entityId) "Equipped"
                            else group.container.name,
                            style = MaterialTheme.typography.titleMedium,
                        )
                        if (!group.carried)
                            Text("· Held elsewhere", style = MaterialTheme.typography.bodySmall)
                    }
                    if (group.path.isNotEmpty())
                        Text(
                            group.path.asReversed().joinToString(" / ") { it.name },
                            style = MaterialTheme.typography.bodySmall,
                        )
                }
                items(visible, key = { "${group.container.id}/${it.entityId}" }) { item ->
                    OutlinedCard(onClick = { vm.open(item) }) {
                        Row(
                            Modifier.fillMaxWidth().padding(16.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Column(Modifier.weight(1f)) {
                                Text(item.title, style = MaterialTheme.typography.titleMedium)
                                val meta =
                                    listOfNotNull(
                                        if (item.isContainer == true) "Container" else null,
                                        if (item.bound) "Bound" else null,
                                    ) +
                                        item.tags
                                            .filter { it.value == true }
                                            .take(2)
                                            .map { it.name }
                                if (meta.isNotEmpty())
                                    Text(
                                        meta.joinToString(" · "),
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                            }
                            item.quantity?.let {
                                Text(
                                    "×$it",
                                    Modifier.padding(horizontal = 12.dp),
                                    style = MaterialTheme.typography.labelLarge,
                                )
                            }
                            Icon(
                                painterResource(R.drawable.ic_chevron_right),
                                null,
                                Modifier.size(20.dp),
                            )
                        }
                    }
                }
            }
        }
        if (query.isNotBlank() && found == 0 && state.inventory != null)
            item { Empty("No matching items", "Try a different name or tag.") }
    }
}

@Composable
private fun ItemScreen(state: UiState, vm: InventoryViewModel) {
    val item = state.item ?: return
    var editor by rememberSaveable(item.entityId) { mutableStateOf(false) }
    var draft by rememberSaveable(item.entityId) { mutableStateOf("") }
    var public by rememberSaveable(item.entityId) { mutableStateOf(false) }
    val queued =
        state.queued.filter {
            it.draft.character.key == state.character?.key && it.draft.itemId == item.entityId
        }
    LazyColumn(
        Modifier.fillMaxSize().imePadding(),
        contentPadding = PaddingValues(20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        item {
            Text(item.title, style = MaterialTheme.typography.headlineLarge)
            val owner = state.inventory?.owners?.find { it.id == item.ownerId }?.name
            Text(
                listOfNotNull(item.quantity?.let { "Quantity $it" }, owner?.let { "Owned by $it" })
                    .joinToString(" · "),
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        if (item.tags.any { it.value == true })
            item {
                Text(
                    item.tags.filter { it.value == true }.joinToString(" · ") { it.name },
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.primary,
                )
            }
        item { SectionTitle("Description") }
        val descriptions = item.descriptionsFor(state.locales)
        if (descriptions.isEmpty()) item { Narrative("No description available.") }
        items(descriptions, key = { "description/${it.fromEntity?.id ?: "own"}" }) { description ->
            description.fromEntity?.let {
                Text(
                    "From ${it.name}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Narrative(description.content)
        }
        item { SectionTitle("Stats") }
        if (item.stats.isEmpty())
            item { Text("No stats available.", color = MaterialTheme.colorScheme.onSurfaceVariant) }
        items(item.stats, key = { "stat/${it.name}" }) { stat ->
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(stat.name, Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge)
                Text(
                    stat.value?.toString()?.trim('"') ?: "—",
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.SemiBold,
                )
            }
            HorizontalDivider(
                Modifier.padding(top = 10.dp),
                color = MaterialTheme.colorScheme.outlineVariant,
            )
        }
        item {
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                SectionTitle("Notes")
                TextButton(onClick = { editor = !editor }) {
                    Text(if (editor) "Close editor" else "Add note")
                }
            }
        }
        if (editor)
            item {
                Card {
                    Column(
                        Modifier.fillMaxWidth().padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        OutlinedTextField(
                            draft,
                            { draft = it },
                            Modifier.fillMaxWidth(),
                            label = { Text("Your note") },
                            minLines = 4,
                        )
                        Row(
                            modifier =
                                Modifier.fillMaxWidth()
                                    .toggleable(
                                        value = public,
                                        role = Role.Checkbox,
                                        onValueChange = { public = it },
                                    ),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Checkbox(public, onCheckedChange = null)
                            Text("Everyone can read this")
                        }
                        Text(
                            "Otherwise only this character's players and the campaign's GMs and library administrators can read it.",
                            style = MaterialTheme.typography.bodySmall,
                        )
                        Text(
                            "Notes queue on this phone if you're offline. Keep the app signed in until they sync.",
                            style = MaterialTheme.typography.bodySmall,
                        )
                        Button(
                            onClick = {
                                vm.addNote(draft, public) {
                                    draft = ""
                                    public = false
                                    editor = false
                                }
                            },
                            enabled = draft.isNotBlank() && !state.submitting,
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text(if (state.submitting) "Keeping note…" else "Add note")
                        }
                    }
                }
            }
        items(queued, key = { "pending/${it.id}" }) { note ->
            OutlinedCard {
                Column(
                    Modifier.fillMaxWidth().padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Text(
                        if (note.error == null) "Pending sync" else "Needs attention",
                        style = MaterialTheme.typography.labelLarge,
                        color = MaterialTheme.colorScheme.primary,
                    )
                    Narrative(note.draft.request.content)
                    note.error?.let {
                        Text(it, color = MaterialTheme.colorScheme.error)
                        TextButton(onClick = { vm.retryNote(note.id) }) { Text("Retry") }
                    }
                    // A queued note may already exist remotely if the reader/refresh failed.
                    Text(
                        "Your draft stays here until the server confirms it and its readers.",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }
        }
        items(
            state.notes.filterNot { note -> queued.any { it.id == note.id } },
            key = { "note/${it.id}" },
        ) { note ->
            Card {
                Column(
                    Modifier.fillMaxWidth().padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Text(note.title, style = MaterialTheme.typography.titleMedium)
                    note.payloads
                        .filter { it.kind == "description" }
                        .forEach { Narrative(it.content.orEmpty()) }
                    Text(
                        listOfNotNull(
                                note.author,
                                if (note.isPublic) "Public" else "Character players, GMs & admins",
                            )
                            .joinToString(" · "),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
        if (state.notes.isEmpty() && queued.isEmpty())
            item {
                Text("No downloaded notes yet.", color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
    }
}

@Composable
private fun SectionTitle(text: String) {
    Text(
        text,
        style = MaterialTheme.typography.titleLarge,
        modifier = Modifier.padding(top = 12.dp),
    )
}

@Composable
private fun Empty(title: String, text: String) {
    Column(
        Modifier.fillMaxWidth().padding(vertical = 28.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text(title, style = MaterialTheme.typography.headlineMedium)
        Text(text, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun Narrative(source: String) {
    val color = MaterialTheme.colorScheme.onSurface
    val fontSize = MaterialTheme.typography.bodyLarge.fontSize.value
    val renderer = remember {
        // No HTML, remote image, JavaScript, or formula evaluation plugins.
        // LorenzoScript wikilinks stay readable; their targets are not guessed.
        mutableMapOf<android.content.Context, io.noties.markwon.Markwon>()
    }
    androidx.compose.ui.viewinterop.AndroidView(
        modifier = Modifier.fillMaxWidth(),
        factory = { context ->
            android.widget.TextView(context).apply {
                setTextIsSelectable(true)
                typeface =
                    android.graphics.Typeface.createFromAsset(context.assets, "fonts/geist.ttf")
                setLineSpacing(0f, 1.25f)
            }
        },
        update = { view ->
            view.setTextColor(color.toArgb())
            view.textSize = fontSize
            val markdown =
                renderer.getOrPut(view.context) {
                    io.noties.markwon.Markwon.builder(view.context)
                        .usePlugin(io.noties.markwon.ext.strikethrough.StrikethroughPlugin.create())
                        .build()
                }
            markdown.setMarkdown(view, source)
        },
    )
}
