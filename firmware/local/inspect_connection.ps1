$ErrorActionPreference = 'Stop'
# Read-only Windows inventory; do not modify drivers, COM settings or devices.
Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match 'VID_0403|FTDIBUS' } | ForEach-Object {
    $_ | Format-List Status,Class,FriendlyName,InstanceId
    Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName `
        DEVPKEY_Device_HardwareIds,DEVPKEY_Device_Service,DEVPKEY_Device_Parent,`
        DEVPKEY_Device_ProblemCode,DEVPKEY_Device_DriverInfPath | Select-Object KeyName,Data | Format-List
}
Get-CimInstance Win32_PnPSignedDriver | Where-Object { $_.DeviceID -match 'VID_0403|FTDIBUS' } |
    Select-Object DeviceName,DeviceID,DriverProviderName,DriverVersion,InfName,IsSigned | Format-List
