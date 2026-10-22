#define AppName "GPT PC Control"
#define AppVersion "1.0.0"
#define AppExe "GPT-PC-Control.exe"

[Setup]
AppId={{DB309293-32A8-4370-8CD7-F3B8CDCA4AA9}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=GPT PC Control Contributors
DefaultDirName={localappdata}\Programs\GPT PC Control
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.22000
OutputDir=..\dist\installer
OutputBaseFilename=GPT-PC-Control-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExe}
LicenseFile=..\LICENSE
CloseApplications=yes

[Languages]
Name: "vietnamese"; MessagesFile: "compiler:Default.isl,windows-vietnamese.isl"

[Tasks]
Name: "desktopicon"; Description: "Tạo biểu tượng ngoài Desktop"; Flags: checkedonce

[Files]
Source: "..\dist\GPT-PC-Control\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\GPT PC Control"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\GPT PC Control"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Mở GPT PC Control"; Flags: nowait postinstall skipifsilent
