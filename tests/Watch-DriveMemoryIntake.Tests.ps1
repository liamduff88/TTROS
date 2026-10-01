# Revisit: when the Windows Drive Memory Intake watcher selection changes. Created 2026-09-23.
# Run with Invoke-Pester on Windows; all files and helper results are local fixtures.

Describe 'Watch-DriveMemoryIntake exact file selection' {
    BeforeEach {
        $global:IntakeTestCalls = [System.Collections.Generic.List[string]]::new()
        $global:IntakeTestDuplicates = @{}
        $inbox = Join-Path $TestDrive 'Inbox'
        if (Test-Path -LiteralPath $inbox) {
            Remove-Item -LiteralPath $inbox -Recurse -Force
        }
        New-Item -ItemType Directory -Path $inbox -Force | Out-Null
        $staging = Join-Path $TestDrive 'queue/inbox/staging/drive'
        if (Test-Path -LiteralPath $staging) {
            Remove-Item -LiteralPath $staging -Recurse -Force
        }
        $watcher = Join-Path $PSScriptRoot '../tools/Watch-DriveMemoryIntake.ps1'
        $source = Get-Content -LiteralPath $watcher -Raw
        $root = ([string]$TestDrive).Replace("'", "''")
        $inboxLiteral = $inbox.Replace("'", "''")
        $source = $source -replace '(?m)^\$Inbox = .+$', ('$Inbox = ' + "'$inboxLiteral'")
        $source = $source -replace '(?m)^\$WslRoot = .+$', ('$WslRoot = ' + "'$root'")
        $fixtureWatcher = Join-Path $TestDrive 'watcher.ps1'
        Set-Content -LiteralPath $fixtureWatcher -Value $source

        function global:wsl.exe {
            $action = if ($args -contains 'ingest') { 'ingest' } else { 'check' }
            $nameIndex = [Array]::IndexOf($args, '--name-b64')
            $name = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($args[$nameIndex + 1]))
            $global:IntakeTestCalls.Add("$action`:$name")
            $global:LASTEXITCODE = 0
            if ($action -eq 'ingest') { return '{"status":"ingested"}' }
            if ($global:IntakeTestDuplicates.ContainsKey($name)) { return '{"status":"reconciled"}' }
            return '{"status":"eligible"}'
        }
        Mock Start-Sleep {}
    }

    AfterEach {
        Remove-Item Function:\wsl.exe -ErrorAction SilentlyContinue
        Remove-Variable IntakeTestCalls, IntakeTestDuplicates -Scope Global -ErrorAction SilentlyContinue
    }

    It 'reconciles only the exact selected candidate and leaves other eligible files untouched' {
        Set-Content -LiteralPath (Join-Path $inbox 'sentinel.md') -Value '# sentinel'
        Set-Content -LiteralPath (Join-Path $inbox 'other.md') -Value '# other'
        $result = & $fixtureWatcher -FileName 'sentinel.md' -Once
        ($result -join ' ') | Should Match 'Eligible sentinel\.md sha256:.*reconciliation only'
        ($global:IntakeTestCalls -join ',') | Should BeExactly 'check:sentinel.md'
        Test-Path -LiteralPath (Join-Path $TestDrive 'queue/inbox/staging/drive') | Should Be $false
    }

    It 'reconciles a selected duplicate and never enters ingestion' {
        Set-Content -LiteralPath (Join-Path $inbox 'duplicate.md') -Value '# duplicate'
        Set-Content -LiteralPath (Join-Path $inbox 'other.md') -Value '# other'
        $global:IntakeTestDuplicates['duplicate.md'] = $true
        $result = & $fixtureWatcher -FileName 'duplicate.md' -Once -Ingest
        ($result -join ' ') | Should Match 'Reconciled duplicate\.md'
        ($global:IntakeTestCalls -join ',') | Should BeExactly 'check:duplicate.md'
    }

    It 'allows only a selected new file into the existing ingestion path' {
        Set-Content -LiteralPath (Join-Path $inbox 'sentinel.md') -Value '# sentinel'
        $other = Join-Path $inbox 'other.md'
        Set-Content -LiteralPath $other -Value '# other'
        $otherHash = (Get-FileHash -LiteralPath $other -Algorithm SHA256).Hash
        $result = & $fixtureWatcher -FileName 'sentinel.md' -Once -Ingest
        ($result -join ' ') | Should Match 'ingested sentinel\.md'
        ($global:IntakeTestCalls -join ',') | Should BeExactly 'check:sentinel.md,ingest:sentinel.md'
        (Get-ChildItem -LiteralPath (Join-Path $TestDrive 'queue/inbox/staging/drive') -Recurse -File).Count | Should Be 1
        (Get-FileHash -LiteralPath $other -Algorithm SHA256).Hash | Should BeExactly $otherHash
    }

    It 'keeps the unselected default behavior' {
        Set-Content -LiteralPath (Join-Path $inbox 'one.md') -Value '# one'
        Set-Content -LiteralPath (Join-Path $inbox 'two.md') -Value '# two'
        $result = & $fixtureWatcher -Once
        ($result -join ' ') | Should Match 'Eligible one\.md'
        ($result -join ' ') | Should Match 'Eligible two\.md'
        (($global:IntakeTestCalls | Sort-Object) -join ',') | Should BeExactly 'check:one.md,check:two.md'
    }

    It 'fails clearly when the exact selected name does not exist' {
        Set-Content -LiteralPath (Join-Path $inbox 'other.md') -Value '# other'
        $caught = $null
        try { & $fixtureWatcher -FileName 'missing.md' -Once -Ingest | Out-Null } catch { $caught = $_ }
        ($null -ne $caught) | Should Be $true
        $caught.Exception.Message | Should Match 'Selected Drive Memory Intake file does not exist: missing\.md'
        $global:IntakeTestCalls.Count | Should Be 0
    }

    It 'rejects a case mismatch to the exact selected name' {
        Set-Content -LiteralPath (Join-Path $inbox 'Other.md') -Value '# other'
        $caught = $null
        try { & $fixtureWatcher -FileName 'other.md' -Once -Ingest | Out-Null } catch { $caught = $_ }
        ($null -ne $caught) | Should Be $true
        $caught.Exception.Message | Should Match 'Selected Drive Memory Intake file does not exist with exact name: other\.md'
        $global:IntakeTestCalls.Count | Should Be 0
    }

    It 'rejects a path in place of a filename' {
        $caught = $null
        try { & $fixtureWatcher -FileName '../other.md' -Once -Ingest | Out-Null } catch { $caught = $_ }
        ($null -ne $caught) | Should Be $true
        $caught.Exception.Message | Should Match 'one exact filename'
        $global:IntakeTestCalls.Count | Should Be 0
    }
}
