package io.lorenzo.inventory

import android.graphics.Bitmap
import android.graphics.Color
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asAndroidBitmap
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.viewModelScope
import androidx.room.Room
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import io.lorenzo.inventory.core.*
import io.lorenzo.inventory.data.*
import io.lorenzo.inventory.ui.*
import java.io.ByteArrayOutputStream
import java.io.File
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class InformationComposerTest {
    @get:Rule val compose = createComposeRule()

    @Test
    fun mixedNoteUsesNativePicturesAndQuietAudienceControls() =
        runBlocking<Unit> {
            val context = InstrumentationRegistry.getInstrumentation().targetContext
            val db = Room.inMemoryDatabaseBuilder(context, InventoryDatabase::class.java).build()
            val cipher = DeviceCipher()
            val credentials =
                object : CredentialStore {
                    override val token = MutableStateFlow<String?>("test-only")

                    override fun save(token: String) {
                        this.token.value = token
                    }

                    override fun clear() {
                        token.value = null
                    }
                }
            val repo =
                InventoryRepository(
                    db.inventoryDao(),
                    credentials,
                    cipher,
                    "http://127.0.0.1:1",
                    {},
                    {},
                )
            val character = Character("test-library", "test-character", "Iria")
            repo.startComposer(character, "test-item", "en-US")
            repo.changeComposer(character, "test-item") {
                it.copy(
                    parts =
                        it.parts.map { part -> part.copy(text = "The western passage is flooded.") }
                )
            }
            val bitmap =
                Bitmap.createBitmap(600, 300, Bitmap.Config.ARGB_8888).apply {
                    eraseColor(Color.rgb(54, 85, 76))
                }
            val bytes =
                ByteArrayOutputStream()
                    .also { bitmap.compress(Bitmap.CompressFormat.JPEG, 90, it) }
                    .toByteArray()
            bitmap.recycle()
            repo.finishCapture(repo.beginCapture(character, "test-item", false), bytes)
            val draft = repo.observeComposer(character, "test-item").first()!!
            val secrets = SecretStore(context, cipher).apply { clear() }
            lateinit var vm: InventoryViewModel
            compose.runOnUiThread { vm = InventoryViewModel(repo, secrets, SavedStateHandle()) }
            var acquired: Boolean? = null
            try {
                compose.setContent {
                    LorenzoTheme {
                        Column(Modifier.verticalScroll(rememberScrollState())) {
                            InformationComposer(
                                UiState(
                                    composer = draft,
                                    recipients = listOf(Recipient("group", "The Cartographers")),
                                ),
                                vm,
                                { acquired = it },
                                {},
                            )
                        }
                    }
                }
                compose.onNodeWithText("The western passage is flooded.").assertExists()
                compose.waitUntil(10000) {
                    compose
                        .onAllNodesWithContentDescription("Attached picture; tap to enlarge")
                        .fetchSemanticsNodes()
                        .isNotEmpty()
                }
                compose
                    .onNodeWithContentDescription("Attached picture; tap to enlarge")
                    .performScrollTo()
                    .performClick()
                compose.onNodeWithText("Close picture").assertExists().performClick()
                compose.onNodeWithText("Gallery").performScrollTo().performClick()
                assertEquals(false, acquired)
                compose.onNodeWithText("Take photo").performClick()
                assertEquals(true, acquired)
                compose.onNodeWithText("Who can read this").performScrollTo().performClick()
                compose.onNodeWithText("The Cartographers").performScrollTo().assertExists()
                val screenshot = compose.onRoot().captureToImage().asAndroidBitmap()
                File(context.getExternalFilesDir(null), "information-composer.png")
                    .outputStream()
                    .use { screenshot.compress(Bitmap.CompressFormat.PNG, 100, it) }
            } finally {
                compose.runOnUiThread { vm.viewModelScope.cancel() }
                db.close()
            }
        }
}
