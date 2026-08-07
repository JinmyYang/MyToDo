; MyToDo 安装脚本(Inno Setup 6)
;
; 编译: "<Inno Setup 6>\ISCC.exe" mytodo.iss
; 产物: release\MyToDo-Setup-v{版本号}.exe
;
; 仅当前用户安装(不弹 UAC),默认目录 %LOCALAPPDATA%\Programs\MyToDo;
; 用户数据在 %APPDATA%\MyToDo,安装/更新/卸载均不触碰。
; 发新版时只改 MyAppVersion;AppId 是升级/卸载的注册表标识,永远不要改。

#define MyAppName "MyToDo"
#define MyAppVersion "1.1.0"
#define MyAppPublisher "JinmyYang"
#define MyAppURL "https://jinmyyang.github.io/MyToDo/"

[Setup]
AppId={{B7F4C9D2-5A1E-4E8C-9F3B-6D0A2C8E1F47}
AppName={#MyAppName}
AppVersion=v{#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\{#MyAppName}
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
OutputDir=release
OutputBaseFilename=MyToDo-Setup-v{#MyAppVersion}
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\MyToDo.exe
UninstallDisplayName={#MyAppName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
; 简体中文放第一位,安装向导默认选中
Name: "chinesesimplified"; MessagesFile: "installer\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; PyInstaller onedir 产物整目录安装
Source: "dist\MyToDo\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\MyToDo.exe"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\MyToDo.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\MyToDo.exe"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[CustomMessages]
DeleteUserDataPrompt=是否同时删除用户数据（任务与设置）？数据位于 %APPDATA%\MyToDo。
english.DeleteUserDataPrompt=Also delete user data (tasks and settings)? Data is stored in %APPDATA%\MyToDo.

[Code]
// 卸载完成后询问是否一并删除用户数据(静默卸载不打扰)
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if (CurUninstallStep = usPostUninstall) and (not UninstallSilent) then
  begin
    DataDir := ExpandConstant('{userappdata}\MyToDo');
    if DirExists(DataDir) then
    begin
      if MsgBox(CustomMessage('DeleteUserDataPrompt'), mbConfirmation, MB_YESNO) = IDYES then
        DelTree(DataDir, True, True, True);
    end;
  end;
end;
