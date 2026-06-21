<#
.SYNOPSIS
  Package Anchor skill source trees into distributable .skill bundles.

.DESCRIPTION
  Each skill's source of truth lives unzipped under skills/src/<name>/ (SKILL.md +
  references/). A ".skill" file is simply a ZIP whose internal layout is
  "<name>/SKILL.md", "<name>/references/*.md" - the format Anthropic Agent Skills use.

  This script zips skills/src/<name>/ back into skills/<name>.skill, preserving that
  internal "<name>/..." path layout. Run it after editing any skill source; the
  PostToolUse hook in .claude/settings.json calls it automatically on save.

.PARAMETER Name
  Optional single skill to pack (folder name under skills/src/). Omit to pack all.

.EXAMPLE
  pwsh skills/pack-skills.ps1                 # rebuild every .skill
  pwsh skills/pack-skills.ps1 bd-legal-answer # rebuild just one
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Name
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$skillsRoot = $PSScriptRoot
$srcRoot = Join-Path $skillsRoot 'src'

if (-not (Test-Path $srcRoot)) {
    Write-Error "Source tree not found: $srcRoot"
    exit 1
}

if ($Name) {
    $dirs = @(Get-Item (Join-Path $srcRoot $Name) -ErrorAction Stop)
} else {
    $dirs = Get-ChildItem -Path $srcRoot -Directory
}

foreach ($dir in $dirs) {
    $skillName = $dir.Name
    $skillMd = Join-Path $dir.FullName 'SKILL.md'
    if (-not (Test-Path $skillMd)) {
        Write-Warning "Skipping $skillName - no SKILL.md"
        continue
    }

    $dest = Join-Path $skillsRoot "$skillName.skill"
    if (Test-Path $dest) { Remove-Item $dest -Force }

    # Build the zip with entries rooted at "<name>/..." so the bundle matches the
    # established layout. Files are added individually to control entry paths and to
    # keep forward-slash separators regardless of OS.
    $zip = [System.IO.Compression.ZipFile]::Open($dest, [System.IO.Compression.ZipArchiveMode]::Create)
    try {
        $files = Get-ChildItem -Path $dir.FullName -Recurse -File
        foreach ($f in $files) {
            $rel = $f.FullName.Substring($dir.FullName.Length).TrimStart('\', '/')
            $entryPath = "$skillName/" + ($rel -replace '\\', '/')
            [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                $zip, $f.FullName, $entryPath,
                [System.IO.Compression.CompressionLevel]::Optimal) | Out-Null
        }
    } finally {
        $zip.Dispose()
    }

    $count = $files.Count
    Write-Host "Packed $skillName.skill with $count files"
}
