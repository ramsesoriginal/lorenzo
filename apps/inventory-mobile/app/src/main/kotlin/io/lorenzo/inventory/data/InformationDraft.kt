package io.lorenzo.inventory.data

import io.lorenzo.inventory.core.*
import java.util.UUID
import kotlinx.serialization.Serializable

@Serializable
data class DraftPart(
    val id: String = UUID.randomUUID().toString(),
    val kind: String = "description",
    val text: String = "",
    val mediaId: String? = null,
)

@Serializable
data class InformationDraft(
    val id: String = UUID.randomUUID().toString(),
    val character: Character,
    val itemId: String,
    val locale: String,
    val parts: List<DraftPart> = listOf(DraftPart()),
    val audience: Audience = Audience(entityIds = listOf(character.entityId)),
    val firstPayloadId: String? = null,
    val orderBase: List<String>? = null,
) {
    val hasContent
        get() = parts.any { it.kind == "picture" || it.text.isNotBlank() }
}

@Serializable
data class CaptureBinding(
    val id: String = UUID.randomUUID().toString(),
    val draftId: String,
    val composerKey: String,
    val camera: Boolean,
    val launched: Boolean = false,
)
