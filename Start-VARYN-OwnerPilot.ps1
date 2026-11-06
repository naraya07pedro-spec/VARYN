# VARYN 17S-44 owner-only Windows Portable pilot launcher.
# This script is unsigned. Run only if independently verified, never as admin.
# No credentials passed as arguments, stored to disk, or displayed.
[CmdletBinding()]
param(
    [ValidateSet('offline','openrouter','deepseek','9router')]
    [string]$Provider = 'offline',
    [switch]$VerifyOnly
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$keys = @(
    'OPENROUTER_API_KEY','DEEPSEEK_API_KEY','VARYN_9ROUTER_API_KEY',
    'OPENAI_API_KEY','ANTHROPIC_API_KEY','GEMINI_API_KEY','GOOGLE_API_KEY',
    'AZURE_OPENAI_API_KEY','GH_TOKEN','GITHUB_TOKEN',
    'AWS_ACCESS_KEY_ID','AWS_SECRET_ACCESS_KEY',
    'SUPABASE_SERVICE_ROLE_KEY','CLOUDFLARE_API_TOKEN'
)
$vars = @{
    openrouter = 'OPENROUTER_API_KEY'
    deepseek = 'DEEPSEEK_API_KEY'
    '9router' = 'VARYN_9ROUTER_API_KEY'
}
$root = $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($root)) {
    Write-Error 'BLOCKED: launch from the extracted portable folder.'
    exit 2
}

function Get-PortableSha256 {
    param([string]$Path)
    $algorithm = [Security.Cryptography.SHA256]::Create()
    $stream = [IO.File]::OpenRead($Path)
    try {
        return [BitConverter]::ToString($algorithm.ComputeHash($stream)).
            Replace('-','').ToLowerInvariant()
    }
    finally {
        $stream.Dispose()
        $algorithm.Dispose()
    }
}

function Assert-VerifiedPortable {
    param([string]$Folder)
    $exe = Join-Path $Folder 'VARYN-Portable.exe'
    $manifestFile = Join-Path $Folder 'BUNDLE-SHA256.json'
    if (-not (Test-Path -LiteralPath $exe -PathType Leaf) -or
        -not (Test-Path -LiteralPath $manifestFile -PathType Leaf) -or
        -not (Test-Path -LiteralPath (Join-Path $Folder '_internal') -PathType Container)) {
        throw 'Incomplete portable folder: EXE/runtime/manifest missing'
    }
    $manifest = Get-Content -LiteralPath $manifestFile -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($manifest.format -cne 'varyn.windows_portable_sha256.v1' -or
        $manifest.publisher_codesign_verified -ne $false -or
        $manifest.human_owner_acceptance_verified -ne $false -or
        $manifest.official_consumer_history_two_way_sync_verified -ne $false) {
        throw 'Unrecognized or misleading unsigned portable manifest'
    }
    $expected = @{}
    foreach ($property in $manifest.files.PSObject.Properties) {
        $name = [string]$property.Name
        $sha = [string]$property.Value
        if ([string]::IsNullOrWhiteSpace($name) -or
            $name.StartsWith('/') -or $name.Contains('\') -or
            $name -match '(^|/)\.\.?(/|$)' -or
            $sha -notmatch '^[0-9a-f]{64}$' -or
            $expected.ContainsKey($name)) {
            throw 'Invalid expected portable path or file hash'
        }
        $expected[$name] = $sha
    }
    if (-not $expected.ContainsKey('VARYN-Portable.exe') -or
        -not $expected.ContainsKey('Start-VARYN-OwnerPilot.ps1') -or
        -not $expected.ContainsKey('README-PORTABLE.txt')) {
        throw 'Portable manifest omitted required owner launcher/executable'
    }
    if ($manifest.file_count -ne $expected.Count) {
        throw 'Portable manifest file count mismatch'
    }
    $seen = @{}
    $folderPrefix = [IO.Path]::GetFullPath($Folder).TrimEnd([char[]]@('\','/')) + [IO.Path]::DirectorySeparatorChar
    foreach ($item in @(Get-ChildItem -LiteralPath $Folder -Force -Recurse)) {
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'Portable symlink/reparse point is not permitted'
        }
        if ($item.PSIsContainer) { continue }
        $path = [IO.Path]::GetFullPath($item.FullName)
        if (-not $path.StartsWith($folderPrefix,[StringComparison]::OrdinalIgnoreCase)) {
            throw 'Portable file outside extracted root'
        }
        $relative = $path.Substring($folderPrefix.Length).Replace('\','/')
        if ($relative -ceq 'BUNDLE-SHA256.json') { continue }
        if (-not $expected.ContainsKey($relative) -or $seen.ContainsKey($relative)) {
            throw 'Unexpected or duplicate portable file'
        }
        $actualHash = Get-PortableSha256 -Path $path
        if ($actualHash -cne $expected[$relative]) {
            throw 'Portable file SHA256 mismatch'
        }
        $seen[$relative] = $true
    }
    if ($seen.Count -ne $expected.Count) {
        throw 'Portable file missing compared with manifest'
    }
    $exeHash = Get-PortableSha256 -Path $exe
    if ($exeHash -cne [string]$manifest.main_executable_sha256) {
        throw 'Portable EXE SHA256 does not match manifest'
    }
    return $exe
}

try {
    if ($env:OS -cne 'Windows_NT') {
        throw 'Windows required'
    }
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    if ((-not $VerifyOnly) -and
        $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Must run as normal non-elevated Windows user'
    }

    $exe = Assert-VerifiedPortable -Folder $root
    Write-Host 'PASS: local file inventory matches the adjacent UNSIGNED manifest.'
    Write-Host 'This is NOT a publisher signature. Cross-check the ZIP SHA256 with the exact GitHub Actions artifact.'
    if ($VerifyOnly) { exit 0 }

    # Credential values inherited from the shell never leak into offline mode.
    foreach ($name in $keys) {
        [Environment]::SetEnvironmentVariable($name, $null, 'Process')
    }

    if ($Provider -ne 'offline') {
        $name = $vars[$Provider]
        Write-Host ('Selected provider: ' + $Provider)
        Write-Host 'Key stays in this process and the launched VARYN child only; never paste into ChatGPT or GitHub.'
        $secure = Read-Host ('Enter YOUR official ' + $Provider + ' API key (hidden)') -AsSecureString
        if ($null -eq $secure -or $secure.Length -lt 1) {
            throw 'Empty credential; no application launched'
        }
        $pointer = [IntPtr]::Zero
        $plain = $null
        try {
            $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
            $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
            if ([string]::IsNullOrWhiteSpace($plain)) {
                throw 'Empty credential; no application launched'
            }
            [Environment]::SetEnvironmentVariable($name, $plain, 'Process')
        }
        finally {
            $plain = $null
            $secure.Dispose()
            if ($pointer -ne [IntPtr]::Zero) {
                [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
            }
        }
    }

    # No secret in command line, disk, logs, shell history or source.
    $process = Start-Process -FilePath $exe -WorkingDirectory $root -PassThru
    if ($null -eq $process -or $process.Id -le 0) {
        throw 'VARYN launch did not return a process'
    }
    Write-Host ('VARYN started locally in ' + $Provider + ' mode.')
    Write-Host 'Network requests still require separate explicit approval INSIDE VARYN.'
    exit 0
}
catch {
    # Verification-only cannot access a provider key or issue a request. The
    # error is from checking local package files; useful for owner/CI triage.
    # For actual key-bearing launch, do not print exception contents.
    if ($VerifyOnly) {
        Write-Host ('VERIFY-ONLY CHECK: ' + $_.Exception.GetType().Name +
                    ': ' + $_.Exception.Message)
    }
    Write-Host 'BLOCKED: Portable verification, permissions or launch failed.'
    Write-Host 'Do not disable Defender/SmartScreen or elevate the launcher.'
    exit 3
}
finally {
    foreach ($name in $keys) {
        [Environment]::SetEnvironmentVariable($name, $null, 'Process')
    }
}
