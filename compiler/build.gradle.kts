plugins {
    kotlin("jvm")
    antlr
    application
}

repositories { mavenCentral() }

dependencies {
    antlr("org.antlr:antlr4:4.13.2")
    implementation("org.antlr:antlr4-runtime:4.13.2")
    testImplementation(kotlin("test-junit5"))
    testRuntimeOnly("org.junit.jupiter:junit-jupiter-engine:5.11.4")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher:1.11.4")
}

kotlin { jvmToolchain(17) }

tasks.generateGrammarSource {
    arguments = arguments + listOf("-visitor", "-no-listener", "-package", "embedlang.parser")
}

tasks.compileKotlin { dependsOn(tasks.generateGrammarSource) }
tasks.compileTestKotlin { dependsOn(tasks.generateTestGrammarSource) }

sourceSets.test {
    kotlin.srcDir(rootProject.file("tests/src/test/kotlin"))
    resources.srcDir(rootProject.file("examples"))
    resources.srcDir(rootProject.file("tests/src/test/resources"))
}

tasks.test {
    useJUnitPlatform()
    doFirst { systemProperty("embedlang.cli.classpath", sourceSets.main.get().runtimeClasspath.asPath) }
}
application {
    mainClass.set("embedlang.MainKt")
    applicationName = "embedlang"
}

// Resolve CLI input paths relative to the repository root on every platform.
tasks.named<JavaExec>("run") { workingDir = rootProject.projectDir }
