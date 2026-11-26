; Inno Setup скрипт — собирает единый Setup.exe для конечного пользователя.
; Положите рядом с этим файлом VBCABLE_Setup_x64.exe (бесплатный, скачивается с vb-audio.com/Cable —
; «Download» без регистрации). Установщик сам поставит драйвер виртуального микрофона в тихом режиме.

#define MyAppName "bomjvoice"
#define MyAppVersion "1.3.0"

[Setup]
AppId={{7B3C9A11-4F2E-4D5A-9C01-B0MJVOICE0001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=bomjvoice
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=..\dist_installer
OutputBaseFilename=bomjvoice-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin

[Files]
Source: "..\dist\bomjvoice.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "VBCABLE_Setup_x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall ignoreversion; Check: CableNeeded

[Tasks]
Name: "desktopicon"; Description: "Значок на рабочем столе"; GroupDescription: "Дополнительно:"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\bomjvoice.exe"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\bomjvoice.exe"; Tasks: desktopicon

[Run]
; Тихая установка драйвера виртуального микрофона (нужен один раз)
Filename: "{tmp}\VBCABLE_Setup_x64.exe"; Parameters: "/S"; StatusMsg: "Установка виртуального микрофона (нужен перезапуск после)…"; Check: CableNeeded; Flags: runhidden waituntilterminated
Filename: "{app}\bomjvoice.exe"; Description: "Запустить bomjvoice"; Flags: postinstall skipifsilent nowait

[Code]
function CableNeeded: Boolean;
begin
  // Драйвер уже есть?
  Result := not (FileExists(ExpandConstant('{sys}\vbcable64.dll'))
             or  FileExists(ExpandConstant('{sys}\vbcable.dll')));
end;

function NeedsRestart: Boolean;
begin
  Result := CableNeeded;
end;
