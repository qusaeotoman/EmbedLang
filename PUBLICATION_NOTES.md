# Public source snapshot exclusions

The original local project and milestone history remain unchanged. This public
snapshot deliberately omits six upstream files because no applicable
redistribution permission was established from the inspected sources:

- `firmware/vendor/SDK-1.1M/SDK_OLED/Core/Src/oled.c`
- `firmware/vendor/SDK-1.1M/SDK_OLED/Core/Src/fonts.c`
- `firmware/vendor/SDK-1.1M/SDK_OLED/Core/Inc/oled.h`
- `firmware/vendor/SDK-1.1M/SDK_OLED/Core/Inc/fonts.h`
- `firmware/vendor/SDK-1.1M/SDK_EXTI/SDK11M.cfg`
- `firmware/vendor/SDK-1.1M/SDK_OLED/SDK_OLED.ioc`

The absence of a license notice is not treated as permission to redistribute.
The remaining vendor files have explicit ST BSD/Apache notices or are covered
by the included SDK_cLAB GPL-3.0 license. Original copyright notices, license
texts and attribution are retained. No project-wide license is assigned to the
original EmbedLang code.

The vendor manifest lists only the 72 included upstream files. The original
hardware tests used the complete local snapshot, with 78 vendor entries. The
public compiler, cLAB build and local Blink build remain available; OLED builds
and OLED firmware integration tests need separately permitted copies of the
four OLED/font files at their documented paths. They are not downloaded by the
public builder. Do not assume that public availability of upstream code grants
redistribution permission. Obtain permission or use a separately reviewed,
licensed replacement before redistributing that component.

The preserved OLED hardware validation is historical evidence, not a claim
that the restricted driver/font files are included in this public repository.
No firmware binaries, Flash backups, logs, tool installations or private
configuration are included. The initial public commit uses the GitHub account's
noreply address, and contains no original private Git history or metadata.

## Verification of this public edition

Before initial publication, the public snapshot passed all 82 compiler JUnit
tests, with zero failures/errors/skips. Its F427 local Blink and ITMO.cLAB
remote_blink firmware builds both completed and passed ELF/BIN verification.
The OLED build is intentionally blocked until separately permitted OLED/font
files are supplied. All generated outputs stayed in ignored build directories.
No board connection, reset, programming or laboratory upload was performed.
