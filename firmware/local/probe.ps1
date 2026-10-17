param(
    [string]$OpenOCD = '.tools/openocd/xpack-openocd-0.12.0-7/bin/openocd.exe',
    [string]$Scripts = '.tools/openocd/xpack-openocd-0.12.0-7/openocd/scripts',
    [ValidateSet('stm32f407vgt6', 'stm32f427vit6')]
    [string]$Mcu = 'stm32f407vgt6'
)
$ErrorActionPreference = 'Stop'
# Run from the repository root. Identification reads only; no reset/halt/write.
$expectedId = if ($Mcu -eq 'stm32f427vit6') { '0x419' } else { '0x413' }
$expectedSize = if ($Mcu -eq 'stm32f427vit6') { 2048 } else { 1024 }
$chip = if ($Mcu -eq 'stm32f427vit6') { 'stm32f427' } else { 'stm32f407' }
# echo/read_memory deliberately exposes values in batch-mode console output.
$checks = 'set id [lindex [read_memory 0xE0042000 32 1] 0]; echo "DBGMCU_IDCODE=$id"; ' +
    'set kib [lindex [read_memory 0x1FFF7A22 16 1] 0]; echo "FLASH_KIB=$kib"; ' +
    'echo "FLASH_OPTCR=[read_memory 0x40023C14 32 1]"; '
if ($Mcu -eq 'stm32f427vit6') { $checks += 'echo "FLASH_OPTCR1=[read_memory 0x40023C18 32 1]"; ' }
$checks += 'if {($id & 0xfff) != ' + $expectedId + ' || $kib != ' + $expectedSize +
    '} {error "MCU identity/capacity does not match selected profile"}; shutdown'
& $OpenOCD -s $Scripts -c 'gdb port disabled' -c 'tcl port disabled' -c 'telnet port disabled' `
    -c "set CHIPNAME $chip" -f firmware/local/openocd/probe.cfg -c 'init' -c $checks
exit $LASTEXITCODE
