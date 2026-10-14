package io.lorenzo.inventory.data

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow

interface PayloadCipher {
    fun encrypt(value: String): String

    fun decrypt(value: String): String
}

interface CredentialStore {
    val token: kotlinx.coroutines.flow.StateFlow<String?>

    fun save(token: String)

    fun clear()
}

/** Android Keystore key never leaves the device; every record has a fresh GCM nonce. */
class DeviceCipher : PayloadCipher {
    private val key: SecretKey =
        synchronized(DeviceCipher::class.java) {
            val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
            (store.getKey("lorenzo.inventory.v1", null) as? SecretKey)
                ?: KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
                    .apply {
                        init(
                            KeyGenParameterSpec.Builder(
                                    "lorenzo.inventory.v1",
                                    KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
                                )
                                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                                .build()
                        )
                    }
                    .generateKey()
        }

    override fun encrypt(value: String): String {
        val cipher =
            Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.ENCRYPT_MODE, key) }
        return Base64.encodeToString(
            cipher.iv + cipher.doFinal(value.toByteArray(Charsets.UTF_8)),
            Base64.NO_WRAP,
        )
    }

    override fun decrypt(value: String): String {
        val bytes = Base64.decode(value, Base64.NO_WRAP)
        return Cipher.getInstance("AES/GCM/NoPadding")
            .apply { init(Cipher.DECRYPT_MODE, key, GCMParameterSpec(128, bytes, 0, 12)) }
            .doFinal(bytes, 12, bytes.size - 12)
            .toString(Charsets.UTF_8)
    }
}

// KTX edit(commit=true) drops commit's Boolean. Publish a token only after a verified write.
@android.annotation.SuppressLint("UseKtx")
class SecretStore(context: Context, private val cipher: PayloadCipher) : CredentialStore {
    private val prefs = context.getSharedPreferences("session", Context.MODE_PRIVATE)
    private val mutableToken =
        MutableStateFlow(
            runCatching { prefs.getString("token", null)?.let(cipher::decrypt) }.getOrNull()
        )
    override val token = mutableToken.asStateFlow()

    override fun save(token: String) {
        check(prefs.edit().putString("token", cipher.encrypt(token)).commit()) {
            "Couldn't save sign-in on this device"
        }
        mutableToken.value = token
    }

    override fun clear() {
        check(prefs.edit().clear().commit()) { "Couldn't remove sign-in" }
        mutableToken.value = null
    }
}
