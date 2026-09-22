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
#>
[CmdletBinding()]
param(
    [string] $Repo = 'EdwardAF-IT/claude-skills',
    [switch] $SkipTools,
    [string] $ClaudeHome = (Join-Path $HOME '.claude'),
    [string] $Stage = (Join-Path $env:LOCALAPPDATA 'claude-skills')
)

$ErrorActionPreference = 'Stop'

function Say([string] $text) { Write-Host ('  ' + $text) }
function Have([string] $name) { return $null -ne (Get-Command $name -ErrorAction SilentlyContinue) }

function Add-UserPath([string] $dir)
{
    $user = [Environment]::GetEnvironmentVariable('PATH', 'User')
    if (($user -split ';') -notcontains $dir)
    {
        [Environment]::SetEnvironmentVariable('PATH', ($user.TrimEnd(';') + ';' + $dir).TrimStart(';'), 'User')
    }
    $env:PATH = $env:PATH + ';' + $dir
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
    winget install --id $id --exact --silent --accept-package-agreements --accept-source-agreements | Out-Null
    # A fresh install is not on this shell's PATH yet; pick it up from the machine and user PATH.
    $env:PATH = [Environment]::GetEnvironmentVariable('PATH', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('PATH', 'User')
    if (-not (Have $command) -and $bin -and (Test-Path $bin)) { Add-UserPath $bin }
    if (-not (Have $command)) { throw ($label + ' installed but ' + $command + ' is not on PATH; open a new window and run this again') }
}

function Ensure-Npm([string] $command, [string] $package, [string] $label)
{
    if (Have $command) { Say ($label + ' present'); return }
    Say ('installing ' + $label + ' ...')
    npm install -g $package | Out-Null
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
    $root = (npm root -g).Trim()
    if (Test-Path (Join-Path $root 'highlight.js')) { Say 'highlight.js present' }
    else { Say 'installing highlight.js ...'; npm install -g highlight.js | Out-Null }
}

# The skills repository lives in a staging folder; the skills are copied from there so
# ~/.claude never becomes a checkout on a family machine.
$stage = $Stage
$url   = 'https://github.com/' + $Repo + '.git'
if (Test-Path (Join-Path $stage '.git'))
{
    Say 'updating skills ...'
    git -C $stage pull --quiet --ff-only
}
else
{
    Say 'fetching skills ...'
    git clone --quiet --depth 1 $url $stage
}

$dest = Join-Path $ClaudeHome 'skills'
New-Item -ItemType Directory -Force -Path $dest | Out-Null
$count = 0
foreach ($dir in Get-ChildItem -Directory (Join-Path $stage 'skills'))
{
    $target = Join-Path $dest $dir.Name
    # Mirror each skill folder on its own, so a skill removed upstream goes, but skills the
    # person added themselves are never touched.
    robocopy $dir.FullName $target /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
    $count++
}

Write-Host ''
Say ($count.ToString() + ' skills in ' + $dest)
if (-not (Test-Path (Join-Path $ClaudeHome '.credentials.json')))
{
    Say 'next: open a new window, run "claude", and sign in when it asks'
}
Write-Host ''
