# Public repository preparation

Historical preparation notes, followed by the recorded publication outcome.

**2026-10-18 source update:** the editor/DWARF/GDB source and reviewed technical
report are now prepared for the approved public-main update. The history below
describes the original publication and earlier approval boundaries; see
[current public edition notes](../PUBLICATION_NOTES.md) for this update's scope,
tests and exclusions. Original private history is not merged or pushed.
The original verified local OLED milestone is
`5f8a6b713b60a2e89089394ab96f6e0200395381`.

## Recorded outcome

The user subsequently approved a clean public snapshot with new Git history.
The published repository is https://github.com/qusaeotoman/EmbedLang, initial
public commit `feeb72965b136fdd7a9cc3f4f310719aaecc47cd` (170 files after the
redistribution review). The original local history was preserved. The six
upstream files excluded from that snapshot and their redistribution constraints
are described in `firmware/THIRD_PARTY.md` and the report appendices.

The sections below describe the **earlier preparation**, not the repository's
current publication status. New editor/report work has not been published;
committing it locally does not authorize another push or release.

## Discovery results

- This checkout has no configured Git remote, so it does not identify a GitHub
  or GitLab publication or establish that any commit was pushed.
- The connected GitHub account is `qusaeotoman`. Its seven accessible owned
  repositories did not include EmbedLang; the exact `qusaeotoman/EmbedLang`
  lookup returned Not Found. Code search found no EmbedLang match there.
- `qusaeotoman/Prog_Lang` is a separate tree-sitter/Python project, not this
  Kotlin/ANTLR compiler.
- Public web searches did not identify this project. The GitLab public API
  could not be queried successfully because of a TLS connection failure.
  No authenticated GitLab account or existing GitLab URL was available.

These checks found no publication to share. They cannot rule out a differently
named, unindexed or private repository on an unconnected account. A known URL
can be checked separately without creating a duplicate.

## Proposed repository

| Setting | Prepared value |
| --- | --- |
| Owner | `qusaeotoman` |
| Name | `EmbedLang` |
| Visibility | Public, only after explicit user approval |
| Description | A Kotlin/ANTLR4 embedded language compiler with typed IR, ARM Thumb-2 generation and hardware-tested STM32 Blink/OLED demos. |
| Suggested topics | `kotlin`, `antlr4`, `compiler`, `embedded-systems`, `stm32`, `cortex-m4`, `thumb2` |
| README | Root `README.md`; historical details retained in `DEVELOPMENT_GUIDE.md` |
| Binaries/releases | None; build locally from source |

The intended address would be `https://github.com/qusaeotoman/EmbedLang`.
It is a proposed address, **not an existing shareable repository**.

## Files and history

The local publication snapshot contains reviewed source, tests, examples,
documentation, the Gradle wrapper and required vendor snapshots/licenses.
It excludes `.git/`, ignored tool installations, binaries, Flash readbacks,
programming logs, credentials and host configuration. The original stable
history is preserved in the working repository.

A scan of all 220 reachable Git blobs found no likely credential patterns or
generated firmware/backup/log paths. It found absolute Windows user paths in
three historical documents. The current versions now use portable relative
paths, but an ordinary push of the existing history would still expose the old
versions. No history rewrite has been performed.

The proposed initial public publication is therefore a **clean source snapshot
with new public history**, leaving all original milestone commits local. It
will include the completed milestone implementation and preparation docs, but
commit `5f8a6b7` itself will not be a commit in that new history. This tradeoff
must be included in the user's publication approval; do not silently push the
old history or rewrite the stable local repository.

`.gitignore` excludes generated firmware/object/map files, logs, backup folders,
private-key/keystore files, environment files, credential configuration and
machine-local editor/tool directories. Exceptions for `.env.example` and
`.env.template` are for non-secret templates only. Ignore rules do not remove
previously tracked content, which is why both the current files and reachable
history were checked. Pattern scans reduce accidental disclosure but cannot
prove that arbitrary data contains no secrets.

The ignored local snapshot and audit evidence are under `.tools/publication/`;
they must never be uploaded as a folder containing tool state or audit logs.
Only the reviewed source snapshot contents are candidates for publication.

## Attribution and license status

Keep all existing third-party notices and `firmware/THIRD_PARTY.md`. The original
EmbedLang code has no selected project-wide license. Some upstream OLED/font
files lack an explicit license notice, as already documented. No MIT, Apache or
other blanket license has been added, and publication preparation does not
resolve those upstream redistribution terms. Review this status when deciding
what to make public; do not label the whole repository under one license.

## Approval boundary and subsequent verification

Before any remote creation or push, show the owner/name, public visibility,
snapshot/history choice and README to the user and obtain explicit approval.
No passwords or tokens should be requested, embedded in commands or committed;
use the connected GitHub account or an authenticated Git client.

After approved publication, verify the actual repository visibility, branch,
uploaded file tree and new public commit. Return the canonical repository URL
and explain which local stable milestone the snapshot represents. If original
history is chosen instead, resolve the historic path disclosures explicitly
before pushing and verify that the approved stable commit is reachable remotely.

No hardware access, compiler changes, programming or remote publication is part
of this preparation step. The last complete compiler/firmware regression result
remains 160 passing checks from the verified OLED milestone; only publication
documentation and ignore rules are changed here.
