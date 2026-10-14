package io.lorenzo.inventory.core

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

@Serializable
data class Me(val id: String, val players: List<Seat>, val locales: List<String> = emptyList()) {
    fun characters(): List<Character> =
        players
            .flatMap { seat ->
                seat.characters.map { Character(seat.tenantId, it.entityId, it.name) }
            }
            .distinctBy { it.key }
            .sortedBy { it.name.lowercase() }
}

@Serializable
data class Seat(
    @SerialName("tenant_id") val tenantId: String,
    val characters: List<CharacterSummary>,
)

@Serializable
data class CharacterSummary(@SerialName("entity_id") val entityId: String, val name: String)

@Serializable
data class Character(val tenantId: String, val entityId: String, val name: String) {
    val key: String
        get() = "$tenantId/$entityId"
}

@Serializable data class EntityRef(val id: String, val name: String)

@Serializable
data class Inventory(val groups: List<InventoryGroup>, val owners: List<EntityRef> = emptyList()) {
    val items: List<Item>
        get() = groups.flatMap { it.items }.distinctBy { it.entityId }
}

@Serializable
data class InventoryGroup(
    val container: EntityRef,
    val carried: Boolean,
    val path: List<EntityRef> = emptyList(),
    @SerialName("item_instances") val items: List<Item>,
)

@Serializable
data class Description(
    val content: String,
    val locale: String,
    @SerialName("from_entity") val fromEntity: EntityRef? = null,
)

@Serializable data class Stat(val name: String, val value: JsonElement? = null)

@Serializable data class Tag(val name: String, val value: Boolean? = null)

@Serializable
data class Item(
    @SerialName("entity_id") val entityId: String,
    val title: String,
    val quantity: Int? = null,
    @SerialName("owner_entity_id") val ownerId: String? = null,
    @SerialName("is_container") val isContainer: Boolean? = null,
    val bound: Boolean = false,
    val descriptions: List<Description> = emptyList(),
    @SerialName("physical_stats") val physical: List<Stat> = emptyList(),
    @SerialName("economic_stats") val economic: List<Stat> = emptyList(),
    @SerialName("destroyable_stats") val destroyable: List<Stat> = emptyList(),
    @SerialName("damaging_stats") val damaging: List<Stat> = emptyList(),
    val tags: List<Tag> = emptyList(),
) {
    val stats: List<Stat>
        get() =
            (physical +
                    economic +
                    destroyable +
                    damaging +
                    tags.map {
                        Stat(
                            it.name,
                            it.value?.let { value ->
                                kotlinx.serialization.json.JsonPrimitive(value)
                            },
                        )
                    })
                .distinctBy { it.name }

    fun descriptionsFor(locales: List<String>): List<Description> =
        descriptions
            .groupBy { it.fromEntity?.id }
            .values
            .mapNotNull { candidates ->
                locales.firstNotNullOfOrNull { locale ->
                    candidates.firstOrNull { it.locale.equals(locale, true) }
                        ?: candidates.firstOrNull {
                            it.locale.substringBefore('-').equals(locale.substringBefore('-'), true)
                        }
                } ?: candidates.firstOrNull()
            }

    fun description(locales: List<String>): Description? = descriptionsFor(locales).firstOrNull()
}

@Serializable
data class Payload(val kind: String, val content: String? = null, val locale: String? = null)

@Serializable
data class Information(
    val id: String,
    val title: String,
    val type: String,
    @SerialName("is_public") val isPublic: Boolean,
    @SerialName("updated_at") val updatedAt: String,
    @SerialName("created_by_name") val author: String? = null,
    val payloads: List<Payload> = emptyList(),
)

@Serializable data class Page<T>(val items: List<T>, val total: Int)

@Serializable
data class NoteCreate(
    val id: String,
    val title: String = "Note",
    val type: String = "note",
    @SerialName("is_public") val isPublic: Boolean = false,
    val content: String,
    val locale: String,
)

@Serializable
data class DeviceCode(
    @SerialName("device_code") val deviceCode: String,
    @SerialName("user_code") val userCode: String,
    @SerialName("verification_uri_complete") val verificationUri: String,
    val interval: Int,
    @SerialName("expires_in") val expiresIn: Int,
)

@Serializable data class IssuedToken(@SerialName("access_token") val token: String)

@Serializable
data class Problem(
    val type: String = "",
    val title: String = "Request failed",
    val detail: String? = null,
)
