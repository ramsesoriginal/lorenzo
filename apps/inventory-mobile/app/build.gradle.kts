plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.ksp)
}

val releaseVersion = file("../version.txt").readText().trim()
val versionParts = releaseVersion.split(".").map { it.toInt() }

require(versionParts.size == 3 && versionParts.all { it >= 0 }) {
    "version.txt must contain a stable major.minor.patch version"
}

require(versionParts[1] < 1_000 && versionParts[2] < 1_000) {
    "Minor and patch versions must be below 1,000 for Android version codes"
}

val androidVersionCode =
    versionParts[0].toLong() * 1_000_000 + versionParts[1] * 1_000 + versionParts[2] + 1

require(androidVersionCode in 1..2_100_000_000L) {
    "Android version code must be within Google Play's supported range"
}

android {
    namespace = "io.lorenzo.inventory"
    buildToolsVersion = "36.0.0"
    compileSdk { version = release(37) { minorApiLevel = 0 } }
    defaultConfig {
        applicationId = "io.lorenzo.inventory"
        minSdk = 28
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        targetSdk = 37
        versionCode = androidVersionCode.toInt()
        versionName = releaseVersion
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
    androidTestImplementation(platform(libs.compose.bom))
    androidTestImplementation(libs.android.test.runner)
    androidTestImplementation(libs.android.test.junit)
    androidTestImplementation(libs.compose.test)
    // Compose's transitive Espresso predates the API 37 input manager change.
    androidTestImplementation(libs.espresso)
    debugImplementation(libs.compose.test.manifest)
    testImplementation(libs.junit)
    testImplementation(libs.mockwebserver)
    testImplementation(libs.coroutines.test)
}
