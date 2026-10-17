plugins {
    kotlin("jvm") version "2.2.21" apply false
    base
}

tasks.named("check") { dependsOn(":compiler:check") }
tasks.named("assemble") { dependsOn(":compiler:assemble") }
