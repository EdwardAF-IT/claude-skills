<#
.SYNOPSIS
  Install or update Claude Code plus Edward's custom skills on a Windows box.

.DESCRIPTION
  One line from an ordinary PowerShell window:

    irm https://raw.githubusercontent.com/EdwardAF-IT/claude-skills/main/install.ps1 | iex

  Installs what is missing (git, Node, Python, Graphviz, Claude Code, mermaid-cli,
  highlight.js), then copies the skills into ~/.claude/skills. Safe to run again: it updates
  the skills and leaves everything else under ~/.claude alone (settings, memory, sessions).

.PARAMETER Repo
  The skills repository. Default: EdwardAF-IT/claude-skills.

.PARAMETER SkipTools
  Copy the skills only; do not install or check tools.

.PARAMETER ClaudeHome
  Where Claude Code keeps its home folder. Defaults to ~/.claude. PowerShell's $HOME is
  read-only, so a test run must pass this rather than setting an environment variable.

.PARAMETER Stage
  Where to keep the skills checkout. Defaults to %LOCALAPPDATA%\claude-skills.

.PARAMETER ToolsPath
  A folder placed first on PATH before winget/npm/git/robocopy are looked up. Lets a test run
  point the installer at stub tools instead of the real machine; production runs leave it unset.
#>
[CmdletBinding()]
param(
    [string] $Repo = 'EdwardAF-IT/claude-skills',
    [switch] $SkipTools,
    [string] $ClaudeHome = (Join-Path $HOME '.claude'),
    [string] $Stage = (Join-Path $env:LOCALAPPDATA 'claude-skills'),
    [string] $ToolsPath = ''
)

$ErrorActionPreference = 'Stop'

if ($ToolsPath) { $env:PATH = $ToolsPath.TrimEnd(';') + ';' + $env:PATH }

function Say([string] $text) { Write-Host ('  ' + $text) }

function Have([string] $name)
{
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($null -eq $cmd) { return $false }
    # The Windows Store ships an App Execution Alias stub for `python`/`python3` that exists on
    # PATH by default but only opens the Store when run. Treat it as not installed. Only those
    # names: winget itself is a real alias in the same WindowsApps folder.
    if (($name -in @('python', 'python3')) -and $cmd.Source -and ($cmd.Source -match '\\WindowsApps\\')) { return $false }
    return $true
}

function Add-UserPath([string] $dir)
{
    $user = [Environment]::GetEnvironmentVariable('PATH', 'User')
    if (($user -split ';') -notcontains $dir)
    {
        [Environment]::SetEnvironmentVariable('PATH', ($user.TrimEnd(';') + ';' + $dir).TrimStart(';'), 'User')
    }
    $env:PATH = $env:PATH + ';' + $dir
}

function Sync-MachinePath()
{
    # Pick up a fresh install from the machine and user PATH, without losing the test stub
    # folder (if any) off the front of this session's PATH.
    $env:PATH = [Environment]::GetEnvironmentVariable('PATH', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('PATH', 'User')
    if ($ToolsPath) { $env:PATH = $ToolsPath.TrimEnd(';') + ';' + $env:PATH }
}

function Invoke-Checked([string] $exe, [string[]] $cmdArgs, [string] $onFailMessage, [int] $failAt = 1)
{
    & $exe @cmdArgs | Out-Null
    if ($LASTEXITCODE -ge $failAt)
    {
        throw ($onFailMessage + ' (' + $exe + ' exited with code ' + $LASTEXITCODE + ').')
    }
}

function Ensure-Winget([string] $command, [string] $id, [string] $label, [string] $bin = '')
{
    if (Have $command) { Say ($label + ' present'); return }
    # Installed earlier but never put on PATH (Graphviz does this): add its folder, skip winget.
    if ($bin -and (Test-Path (Join-Path $bin ($command + '.exe'))))
    {
        Add-UserPath $bin
        Say ($label + ' present; added ' + $bin + ' to PATH')
        return
    }
    Say ('installing ' + $label + ' ...')
    Invoke-Checked 'winget' @('install', '--id', $id, '--exact', '--silent', '--accept-package-agreements', '--accept-source-agreements') `
        ($label + ' could not be installed. Check your network connection and try running the installer again')
    Sync-MachinePath
    if (-not (Have $command) -and $bin -and (Test-Path $bin)) { Add-UserPath $bin }
    if (-not (Have $command)) { throw ($label + ' installed but ' + $command + ' is not on PATH yet. Close this window, open a new one, and run the installer again') }
}

function Ensure-Npm([string] $command, [string] $package, [string] $label)
{
    if (Have $command) { Say ($label + ' present'); return }
    Say ('installing ' + $label + ' ...')
    # `npm` alone can resolve to npm.ps1, which PowerShell's default execution policy blocks.
    # npm.cmd is always safe to run.
    Invoke-Checked 'npm.cmd' @('install', '-g', $package) `
        ($label + ' could not be installed. Check your network connection and try running the installer again')
    if (-not (Have $command)) { throw ($label + ' installed but ' + $command + ' is not on PATH yet. Close this window, open a new one, and run the installer again') }
}

Write-Host ''
Write-Host 'Claude Code + skills installer'
Write-Host ''

if (-not $SkipTools)
{
    if (-not (Have 'winget')) { throw 'winget is missing; install "App Installer" from the Microsoft Store and run this again' }
    Ensure-Winget 'git'    'Git.Git'             'git'
    Ensure-Winget 'node'   'OpenJS.NodeJS.LTS'   'Node.js'
    Ensure-Winget 'python' 'Python.Python.3.12'  'Python'
    Ensure-Winget 'dot'    'Graphviz.Graphviz'   'Graphviz' (Join-Path $env:ProgramFiles 'Graphviz\bin')
    Ensure-Npm    'claude' '@anthropic-ai/claude-code'  'Claude Code'
    Ensure-Npm    'mmdc'   '@mermaid-js/mermaid-cli'    'mermaid-cli'
    # highlight.js is a library, not a command; check the global tree for it.
    $root = (& npm.cmd root -g).Trim()
    if (Test-Path (Join-Path $root 'highlight.js')) { Say 'highlight.js present' }
    else
    {
        Say 'installing highlight.js ...'
        Invoke-Checked 'npm.cmd' @('install', '-g', 'highlight.js') `
            'highlight.js could not be installed. Check your network connection and try running the installer again'
    }
}

# The skills repository lives in a staging folder; the skills are copied from there so
# ~/.claude never becomes a checkout on a family machine.
$stage = $Stage
$url   = 'https://github.com/' + $Repo + '.git'
if (Test-Path (Join-Path $stage '.git'))
{
    Say 'updating skills ...'
    Invoke-Checked 'git' @('-C', $stage, 'pull', '--quiet', '--ff-only') `
        'Could not update the skills. Check your network connection and try running the installer again'
}
else
{
    Say 'fetching skills ...'
    Invoke-Checked 'git' @('clone', '--quiet', '--depth', '1', $url, $stage) `
        'Could not download the skills. Check your network connection and try running the installer again'
}

$dest = Join-Path $ClaudeHome 'skills'
New-Item -ItemType Directory -Force -Path $dest | Out-Null

# A manifest of the skill names this installer put in $dest, so an update can tell "retired
# upstream" apart from "the person made this themselves" — robocopy /MIR alone cannot.
$manifestPath = Join-Path $dest '.claude-skills-manifest'
$oldManifest = @()
if (Test-Path $manifestPath) { $oldManifest = @(Get-Content $manifestPath | Where-Object { $_ }) }

$count = 0
$newManifest = @()
foreach ($dir in Get-ChildItem -Directory (Join-Path $stage 'skills'))
{
    $target = Join-Path $dest $dir.Name
    Invoke-Checked 'robocopy' @($dir.FullName, $target, '/MIR', '/NFL', '/NDL', '/NJH', '/NJS', '/NP') `
        ('Could not copy the ' + $dir.Name + ' skill. Check that ' + $dest + ' is not open in another program and try again') `
        8
    $newManifest += $dir.Name
    $count++
}

foreach ($old in $oldManifest)
{
    if (($newManifest -notcontains $old) -and (Test-Path (Join-Path $dest $old)))
    {
        Remove-Item -Recurse -Force (Join-Path $dest $old)
        Say ('removed ' + $old + ' (retired upstream)')
    }
}
$newManifest | Set-Content $manifestPath

# One-time cleanup: `resume` was renamed `pickup` before this manifest existed, so the loop
# above has no record of it. Remove only our own copy, identified by its exact description —
# never a skill the person wrote themselves that happens to share the name.
$oldResume = Join-Path $dest 'resume'
if ((Test-Path $oldResume) -and ($newManifest -notcontains 'resume'))
{
    $skillFile = Join-Path $oldResume 'SKILL.md'
    if (Test-Path $skillFile)
    {
        $text = Get-Content $skillFile -Raw
        if ($text -match '(?m)^name:\s*resume\s*$' -and $text -match 'Pick up a repo where a previous session left it')
        {
            Remove-Item -Recurse -Force $oldResume
            Say 'removed resume (renamed to pickup)'
        }
    }
}

Write-Host ''
# The published version, so someone asked "which do you have?" can answer with one line.
$versionFile = Join-Path $stage 'version'
$version = if (Test-Path $versionFile) { ' (version ' + (Get-Content $versionFile -TotalCount 1).Trim() + ')' } else { '' }
Say ($count.ToString() + ' skills in ' + $dest + $version)

$policy = Get-ExecutionPolicy
if ($policy -in @('Restricted', 'Undefined', 'AllSigned'))
{
    Say 'note: this PC''s PowerShell script policy will block "claude" (and npm) from running here.'
    Say 'fix with: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned'
    Say 'or just run "claude" from Command Prompt (cmd.exe) instead.'
}

if (-not (Test-Path (Join-Path $ClaudeHome '.credentials.json')))
{
    Say 'next: open a new window, run "claude", and sign in when it asks'
}
Write-Host ''
