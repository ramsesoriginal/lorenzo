import org.gradle.api.attributes.Bundling
import org.gradle.api.attributes.Usage

plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.kotlin.jvm) apply false
    alias(libs.plugins.kotlin.compose) apply false
    alias(libs.plugins.kotlin.serialization) apply false
    alias(libs.plugins.ksp) apply false
}

val formatter by
    configurations.creating {
        attributes {
            attribute(Usage.USAGE_ATTRIBUTE, objects.named(Usage.JAVA_RUNTIME))
            attribute(Bundling.BUNDLING_ATTRIBUTE, objects.named(Bundling.SHADOWED))
        }
    }

dependencies { formatter(libs.ktfmt) }

val kotlinSources =
    fileTree(projectDir) {
        include("**/*.kt", "**/*.kts")
        exclude("**/build/**", ".gradle/**")
    }

tasks.register<JavaExec>("formatKotlin") {
    classpath = formatter
    mainClass.set("com.facebook.ktfmt.cli.Main")
    args("--kotlinlang-style")
    args(kotlinSources.files.sorted().map { it.absolutePath })
}

tasks.register<JavaExec>("checkKotlinFormat") {
    classpath = formatter
    mainClass.set("com.facebook.ktfmt.cli.Main")
    args("--kotlinlang-style", "--dry-run", "--set-exit-if-changed")
    args(kotlinSources.files.sorted().map { it.absolutePath })
}
