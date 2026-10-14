plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.ksp)
}

android {
    namespace = "io.lorenzo.inventory"
    compileSdk { version = release(37) { minorApiLevel = 0 } }
    defaultConfig {
        applicationId = "io.lorenzo.inventory"
        minSdk = 28
        targetSdk = 37
        versionCode = 1
        versionName = file("../version.txt").readText().trim()
        buildConfigField(
            "String",
            "API_BASE_URL",
            "\"https://lorenzo-api-100817212329.europe-west1.run.app/\"",
        )
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
    }
    lint { abortOnError = true }
}

ksp { arg("room.schemaLocation", "$projectDir/schemas") }

dependencies {
    implementation(project(":core"))
    implementation(platform(libs.compose.bom))
    implementation(libs.compose.ui)
    implementation(libs.compose.material3)
    implementation(libs.compose.preview)
    debugImplementation(libs.compose.tooling)
    implementation(libs.activity)
    implementation(libs.lifecycle.compose)
    implementation(libs.lifecycle.viewmodel)
    implementation(libs.room.runtime)
    implementation(libs.room.ktx)
    ksp(libs.room.compiler)
    implementation(libs.work)
    implementation(libs.coroutines.android)
    implementation(libs.serialization)
    implementation(libs.okhttp)
    implementation(libs.markwon.core)
    implementation(libs.markwon.strikethrough)
    testImplementation(libs.junit)
    testImplementation(libs.mockwebserver)
    testImplementation(libs.coroutines.test)
}
