package io.lorenzo.inventory

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.getValue
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.compose.LifecycleEventEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.createSavedStateHandle
import androidx.lifecycle.viewmodel.CreationExtras
import androidx.lifecycle.viewmodel.compose.viewModel
import io.lorenzo.inventory.ui.*

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val app = application as InventoryApplication
        setContent {
            val vm: InventoryViewModel =
                viewModel(
                    factory =
                        object : ViewModelProvider.Factory {
                            @Suppress("UNCHECKED_CAST")
                            override fun <T : ViewModel> create(
                                modelClass: Class<T>,
                                extras: CreationExtras,
                            ): T =
                                InventoryViewModel(
                                    app.repository,
                                    app.secrets,
                                    extras.createSavedStateHandle(),
                                )
                                    as T
                        }
                )
            val state by vm.state.collectAsStateWithLifecycle()
            LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { if (state.signedIn) vm.refresh() }
            LorenzoTheme { InventoryScreen(state, vm) }
        }
    }
}
