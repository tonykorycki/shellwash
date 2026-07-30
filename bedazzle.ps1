# Shellwash — shell layer (prompt, buddy, fetch, lava, termbg hooks)
# Dot-sourced from your PowerShell profile. `bedazzle` toggles features.

$global:AD = @{
    Root       = Split-Path -Parent $MyInvocation.MyCommand.Path
    Esc        = [char]27
    CmdCount   = 0
    Durations  = New-Object System.Collections.Generic.List[double]
    Stats      = @{ Fails = 0; Start = Get-Date }
    Static     = $null
    LogoLines  = $null
    BatteryTs  = [datetime]::MinValue
    BatteryVal = $null
    BatteryDead = $false
    LastPrompt = $null
    DailyHat   = $null
}

# ── config ──────────────────────────────────────────────────────────────

function global:AD-DefaultConfig {
    @{
        accent  = 215.0          # hue that runs the show
        sprite  = 'cat'          # buddy name | pixel sprite | random
        hat     = 'daily'        # daily roll | a hat name | none
        features = @{
            fetch     = $true    # system panel on startup
            sprite    = $true    # buddy in the prompt corner
            rightinfo = $true    # duration + status + clock, right-aligned
            git       = $true    # branch (+ merge/rebase state)
            venv      = $true    # active python venv chip
            shortpath = $true    # fish-style path compression
            title     = $true    # tab title follows your folder
            airy      = $true    # breathing room above the prompt
            battery   = $true    # battery %% in right info (laptops)
            weather   = $true    # cached wttr.in temp in fetch + right info
            spirits   = $false   # kaomoji visitors (v1 legacy)
            rule      = $false   # full-width gradient rule (v1 legacy)
        }
    }
}

function global:AD-LoadConfig {
    $cfg = AD-DefaultConfig
    $path = Join-Path $global:AD.Root 'bedazzle.config.json'
    if (Test-Path $path) {
        try {
            $j = Get-Content $path -Raw | ConvertFrom-Json
            if ($null -ne $j.accent) { $cfg.accent = [double]$j.accent }
            if ($j.sprite) { $cfg.sprite = [string]$j.sprite }
            if ($j.hat) { $cfg.hat = [string]$j.hat }
            if ($j.features) {
                foreach ($p in $j.features.PSObject.Properties) {
                    if ($cfg.features.ContainsKey($p.Name)) { $cfg.features[$p.Name] = [bool]$p.Value }
                }
            }
        } catch { }
    }
    $cfg
}

function global:AD-SaveConfig {
    $path = Join-Path $global:AD.Root 'bedazzle.config.json'
    try { $global:AD.Config | ConvertTo-Json -Depth 4 | Set-Content -Path $path -Encoding UTF8 } catch { }
}

function global:AD-On([string]$name) { [bool]$global:AD.Config.features[$name] }

# ── color helpers ───────────────────────────────────────────────────────

function global:AD-HsvToRgb {
    param([double]$h, [double]$s, [double]$v)
    $h = (($h % 360) + 360) % 360
    $c = $v * $s
    $x = $c * (1 - [math]::Abs((($h / 60) % 2) - 1))
    $m = $v - $c
    if ($h -lt 60) { $r = $c; $g = $x; $b = 0 }
    elseif ($h -lt 120) { $r = $x; $g = $c; $b = 0 }
    elseif ($h -lt 180) { $r = 0; $g = $c; $b = $x }
    elseif ($h -lt 240) { $r = 0; $g = $x; $b = $c }
    elseif ($h -lt 300) { $r = $x; $g = 0; $b = $c }
    else { $r = $c; $g = 0; $b = $x }
    , @([int](($r + $m) * 255), [int](($g + $m) * 255), [int](($b + $m) * 255))
}

function global:AD-Fg([int]$r, [int]$g, [int]$b) { "$($global:AD.Esc)[38;2;$r;$g;${b}m" }
function global:AD-Accent([double]$sat = 0.62, [double]$val = 0.98) {
    $rgb = AD-HsvToRgb $global:AD.Config.accent $sat $val
    AD-Fg $rgb[0] $rgb[1] $rgb[2]
}
function global:AD-Accent2 {
    $rgb = AD-HsvToRgb ($global:AD.Config.accent + 55) 0.55 0.95
    AD-Fg $rgb[0] $rgb[1] $rgb[2]
}

function global:AD-Gradient {
    param([string]$Text, [double]$Hue0 = 190, [double]$Span = 130, [double]$Sat = 0.7)
    $e = $global:AD.Esc
    $sb = New-Object System.Text.StringBuilder
    $n = $Text.Length
    for ($i = 0; $i -lt $n; $i++) {
        $rgb = AD-HsvToRgb ($Hue0 + $Span * ($i / [math]::Max(1, $n - 1))) $Sat 1.0
        [void]$sb.Append("$e[38;2;$($rgb[0]);$($rgb[1]);$($rgb[2])m$($Text[$i])")
    }
    [void]$sb.Append("$e[0m")
    $sb.ToString()
}

function global:AD-Rule {
    param([int]$Width, [double]$Hue0)
    if ($Width -lt 1) { return "" }
    $e = $global:AD.Esc
    $sb = New-Object System.Text.StringBuilder
    $chunks = 14
    $per = [math]::Max(1, [math]::Floor($Width / $chunks))
    $done = 0
    for ($i = 0; $i -lt $chunks; $i++) {
        if ($done -ge $Width) { break }
        $len = $per
        if ($i -eq $chunks - 1 -or $done + $len -gt $Width) { $len = $Width - $done }
        $rgb = AD-HsvToRgb ($Hue0 + 150.0 * $i / $chunks) 0.6 0.85
        [void]$sb.Append("$e[38;2;$($rgb[0]);$($rgb[1]);$($rgb[2])m" + ("─" * $len))
        $done += $len
    }
    [void]$sb.Append("$e[0m")
    $sb.ToString()
}

# ── pixel renderer (half-block) ─────────────────────────────────────────

function global:AD-RenderPixels {
    param([string[]]$Rows, [hashtable]$Palette)
    $e = $global:AD.Esc
    $lines = @()
    for ($y = 0; $y -lt $Rows.Count; $y += 2) {
        $topRow = $Rows[$y]
        if ($y + 1 -lt $Rows.Count) { $botRow = $Rows[$y + 1] } else { $botRow = "." * $topRow.Length }
        $sb = New-Object System.Text.StringBuilder
        for ($x = 0; $x -lt $topRow.Length; $x++) {
            $t = $Palette[[string]$topRow[$x]]
            $b = $Palette[[string]$botRow[$x]]
            if ($null -eq $t -and $null -eq $b) { [void]$sb.Append("$e[0m ") }
            elseif ($null -eq $b) { [void]$sb.Append("$e[0m$e[38;2;$($t[0]);$($t[1]);$($t[2])m▀") }
            elseif ($null -eq $t) { [void]$sb.Append("$e[0m$e[38;2;$($b[0]);$($b[1]);$($b[2])m▄") }
            else { [void]$sb.Append("$e[38;2;$($t[0]);$($t[1]);$($t[2]);48;2;$($b[0]);$($b[1]);$($b[2])m▀") }
        }
        [void]$sb.Append("$e[0m")
        $lines += $sb.ToString()
    }
    , $lines
}

# ── buddies: ASCII line-art pets (à la /buddy), state-reactive ──────────
#    Each buddy: 4 rows, an eye row that swaps per state, and a head
#    column for hat placement.
#    States: idle · blink · fail (cmd errored, +!) · happy (long cmd
#    finished, +^^) · sleep (you were away, +zZ)

$global:ADBuddyOrder = @('duck', 'goose', 'blob', 'cat', 'dragon', 'octopus',
    'owl', 'penguin', 'turtle', 'snail', 'ghost', 'axolotl',
    'capybara', 'cactus', 'robot', 'rabbit', 'mushroom', 'chonk')

$global:ADBuddies = @{
    duck = @{
        color = @(255, 223, 92); head = 4; eyeRow = 1
        rows = @('   __', ' <(. )___', '  (  ._> /', '   `---''')
        eyes = @{ blink = ' <(- )___'; fail = ' <(o )___'; happy = ' <(^ )___' }
    }
    goose = @{
        color = @(200, 204, 216); head = 3; eyeRow = 0
        rows = @('  (.>', '  ||', '_(__)_', ' ^^^^')
        eyes = @{ blink = '  (->'; fail = '  (o>'; happy = '  (^>' }
    }
    blob = @{
        color = @(126, 231, 135); head = 4; eyeRow = 1
        rows = @(' .----.', '( .  . )', '(      )', ' `----''')
        eyes = @{ blink = '( -  - )'; fail = '( o  o )'; happy = '( ^  ^ )' }
    }
    cat = @{
        color = @(230, 200, 170); head = 3; eyeRow = 1
        rows = @(' /\_/\', '( .  .)', '(  ω  )', '(")_(")')
        eyes = @{ blink = '( -  -)'; fail = '( o  o)'; happy = '( ^  ^)' }
    }
    dragon = @{
        color = @(248, 110, 90); head = 4; eyeRow = 1
        rows = @(' /^\  /^\', '<  .  .  >', '(   ~~   )', ' `-vvvv-''')
        eyes = @{ blink = '<  -  -  >'; fail = '<  o  o  >'; happy = '<  ^  ^  >' }
    }
    octopus = @{
        color = @(255, 121, 198); head = 4; eyeRow = 1
        rows = @(' .----.', '( .  . )', '(______)', '/\/\/\/\')
        eyes = @{ blink = '( -  - )'; fail = '( o  o )'; happy = '( ^  ^ )' }
    }
    owl = @{
        color = @(210, 180, 140); head = 4; eyeRow = 1
        rows = @(' /\  /\', '((.)(.))', '(  ><  )', ' `----''')
        eyes = @{ blink = '((-)(-))'; fail = '((o)(o))'; happy = '((^)(^))' }
    }
    penguin = @{
        color = @(180, 200, 230); head = 3; eyeRow = 1
        rows = @(' .---.', ' (.>.)', ' /(   )\', '  `---''')
        eyes = @{ blink = ' (->-)'; fail = ' (o>o)'; happy = ' (^>^)' }
    }
    turtle = @{
        color = @(140, 200, 120); head = 3; eyeRow = 1
        rows = @(' _,--._', '( .  . )', '/[______]\', '  ||  ||')
        eyes = @{ blink = '( -  - )'; fail = '( o  o )'; happy = '( ^  ^ )' }
    }
    snail = @{
        color = @(220, 180, 130); head = 6; eyeRow = 0
        rows = @(' .   .--.', '  \ ( @ )', '   \_`--''', ' ~~~~~~~~')
        eyes = @{ blink = ' -   .--.'; fail = ' o   .--.'; happy = ' ^   .--.' }
    }
    ghost = @{
        color = @(187, 154, 247); head = 4; eyeRow = 1
        rows = @(' .----.', '/ .  . \', '|      |', '~`~``~`~')
        eyes = @{ blink = '/ -  - \'; fail = '/ o  o \'; happy = '/ ^  ^ \' }
    }
    axolotl = @{
        color = @(255, 150, 170); head = 5; eyeRow = 1
        rows = @('}~(______)~{', '}~( .  . )~{', '  ( .--. )', '  (_/  \_)')
        eyes = @{ blink = '}~( -  - )~{'; fail = '}~( o  o )~{'; happy = '}~( ^  ^ )~{' }
    }
    capybara = @{
        color = @(200, 160, 110); head = 4; eyeRow = 1
        rows = @(' n_____n', '( .   . )', '(   oo  )', ' `-----''')
        eyes = @{ blink = '( -   - )'; fail = '( o   o )'; happy = '( ^   ^ )' }
    }
    cactus = @{
        color = @(120, 200, 110); head = 4; eyeRow = 1
        rows = @('n  ___  n', '| |. .| |', '|_|   |_|', '  |   |')
        eyes = @{ blink = '| |- -| |'; fail = '| |o o| |'; happy = '| |^ ^| |' }
    }
    robot = @{
        color = @(110, 220, 255); head = 4; eyeRow = 1
        rows = @(' .[|||].', '[ .  . ]', '[ ==== ]', ' `----''')
        eyes = @{ blink = '[ -  - ]'; fail = '[ x  x ]'; happy = '[ ^  ^ ]' }
    }
    rabbit = @{
        color = @(235, 235, 235); head = 4; eyeRow = 1
        rows = @('  (\__/)', ' ( .  . )', '=(  ..  )=', ' (")__(")')
        eyes = @{ blink = ' ( -  - )'; fail = ' ( o  o )'; happy = ' ( ^  ^ )' }
    }
    mushroom = @{
        color = @(255, 130, 120); head = 4; eyeRow = 2
        rows = @('.-o-OO-o-.', '(________)', '  |.  .|', '  |____|')
        eyes = @{ blink = '  |-  -|'; fail = '  |o  o|'; happy = '  |^  ^|' }
    }
    chonk = @{
        color = @(200, 204, 216); head = 4; eyeRow = 1
        rows = @(' /\   /\', '( .   . )', '(   ..  )', ' `-----''')
        eyes = @{ blink = '( -   - )'; fail = '( o   o )'; happy = '( ^   ^ )' }
    }
}

# pixel-art alternates (half-block style)
$global:ADSprites = @{
    slime = @{
        palette = @{
            'g' = @(126, 231, 135); 'd' = @(46, 160, 67); 'b' = @(13, 17, 23)
            'w' = @(240, 255, 244); 'z' = @(120, 130, 170)
        }
        frames = @{
            idle  = @(
                @('..gggggg..', '.gwbggwbg.', 'gggggggggg', '.dddddddd.'),
                @('..........', '.gwbggwbg.', 'gggggggggg', 'dddddddddd')
            )
            blink = @('..gggggg..', '.gggggggg.', 'gggggggggg', '.dddddddd.')
            fail  = @('..gggggg..', '.gbbggbbg.', 'gggggggggg', '.dddddddd.')
            happy = @('..gggggg..', '.gwgggwgg.', 'gggggggggg', '.dddddddd.')
            sleep = @('..gggggg.z', '.gggggggg.', 'gggggggggg', '.dddddddd.')
        }
    }
    flame = @{
        palette = @{
            'r' = @(248, 81, 73); 'o' = @(255, 153, 51); 'y' = @(255, 223, 92)
            'w' = @(255, 250, 220); 'z' = @(120, 130, 170)
        }
        frames = @{
            idle  = @(
                @('....rr....', '..rroor...', '.royyyor..', '..oyyyo...'),
                @('.....r....', '...roor...', '..royyor..', '...oyyo...')
            )
            blink = @('....r.....', '..rror....', '.roywyor..', '..oyyyo...')
            fail  = @('...rrr....', '..rrrrr...', '.rrrrrrr..', '..rrrrr...')
            happy = @('...ryr....', '..ryyyr...', '.ryywyyr..', '..oyyyo...')
            sleep = @('..........', '....o....z', '...oyo....', '..oooo....')
        }
    }
}

# ── hats + rarity ───────────────────────────────────────────────────────

$global:ADHats = @{
    beanie    = @{ art = '(___)'; rarity = 'uncommon' }
    propeller = @{ art = '-+-'; rarity = 'uncommon' }
    tophat    = @{ art = '[___]'; rarity = 'rare' }
    tinyduck  = @{ art = ',>'; rarity = 'rare' }
    crown     = @{ art = '\^^^/'; rarity = 'epic' }
    wizard    = @{ art = '/^\'; rarity = 'epic' }
    halo      = @{ art = '(   )'; rarity = 'legendary' }
}

$global:ADRarityColors = @{
    common    = @(140, 145, 160)
    uncommon  = @(126, 231, 135)
    rare      = @(110, 160, 255)
    epic      = @(190, 130, 255)
    legendary = @(255, 200, 60)
}

function global:AD-RollHat([System.Random]$Rng) {
    # common 60%%: bare head · uncommon 25 · rare 10 · epic 4 · legendary 1
    $roll = $Rng.Next(0, 1000)
    if ($roll -lt 600) { return $null }
    if ($roll -lt 850) { return @('beanie', 'propeller')[$Rng.Next(0, 2)] }
    if ($roll -lt 950) { return @('tophat', 'tinyduck')[$Rng.Next(0, 2)] }
    if ($roll -lt 990) { return @('crown', 'wizard')[$Rng.Next(0, 2)] }
    return 'halo'
}

function global:AD-ComputeDailyHat {
    $seed = [int](Get-Date).ToString('yyyyMMdd')
    foreach ($ch in [char[]]$env:USERNAME) { $seed += [int]$ch * 7 }
    $rng = New-Object System.Random($seed)
    $global:AD.DailyHat = AD-RollHat $rng
}

function global:AD-CurrentHatName {
    $h = $global:AD.Config.hat
    if ($h -eq 'none') { return $null }
    if ($h -eq 'daily') { return $global:AD.DailyHat }
    if ($global:ADHats.ContainsKey($h)) { return $h }
    return $null
}

# ── buddy selection + rendering ─────────────────────────────────────────

function global:AD-PickSprite {
    $want = $global:AD.Config.sprite
    $all = @($global:ADBuddies.Keys) + @($global:ADSprites.Keys)
    if ($want -eq 'random') { $want = $all | Get-Random }
    if ($all -notcontains $want) { $want = 'cat' }
    $global:AD.SpriteName = $want
}

function global:AD-BuddyRows {
    # plain-text rows for a buddy in a given state (hat optional)
    param([string]$Name, [string]$State = 'idle', [bool]$WithHat = $true)
    $b = $global:ADBuddies[$Name]
    $rows = @() + $b.rows
    if ($State -eq 'fail' -and $b.eyes.fail) { $rows[$b.eyeRow] = $b.eyes.fail }
    elseif ((@('blink', 'sleep') -contains $State) -and $b.eyes.blink) { $rows[$b.eyeRow] = $b.eyes.blink }
    elseif ($State -eq 'happy' -and $b.eyes.happy) { $rows[$b.eyeRow] = $b.eyes.happy }
    if ($State -eq 'fail') { $rows[0] = $rows[0] + '  !' }
    if ($State -eq 'sleep') { $rows[0] = $rows[0] + ' zZ' }
    $hatName = $null
    if ($WithHat) { $hatName = AD-CurrentHatName }
    if ($hatName) {
        $art = $global:ADHats[$hatName].art
        $start = [math]::Max(0, $b.head - [math]::Floor($art.Length / 2))
        $rows = @((' ' * $start) + $art) + $rows
    }
    @{ rows = $rows; hat = $hatName }
}

function global:AD-SpriteInfo {
    param([bool]$Ok = $true, [double]$Ms = 0, [double]$IdleSec = 0)
    $e = $global:AD.Esc
    $name = $global:AD.SpriteName
    $state = 'idle'
    if (-not $Ok) { $state = 'fail' }
    elseif ($IdleSec -gt 240) { $state = 'sleep' }
    elseif ($Ms -gt 10000) { $state = 'happy' }
    elseif ((Get-Random -Maximum 7) -eq 0) { $state = 'blink' }

    if ($global:ADBuddies.ContainsKey($name)) {
        $b = $global:ADBuddies[$name]
        $res = AD-BuddyRows -Name $name -State $state
        $rows = $res.rows
        $wdt = 0
        foreach ($r in $rows) { if ($r.Length -gt $wdt) { $wdt = $r.Length } }
        $c = $b.color
        $col = AD-Fg $c[0] $c[1] $c[2]
        $lines = @()
        for ($i = 0; $i -lt $rows.Count; $i++) {
            $txt = $rows[$i].PadRight($wdt)
            if ($res.hat -and $i -eq 0) {
                $hc = $global:ADRarityColors[$global:ADHats[$res.hat].rarity]
                $lines += "$(AD-Fg $hc[0] $hc[1] $hc[2])$txt$e[0m"
            } else {
                $lines += "$col$txt$e[0m"
            }
        }
        return @{ lines = $lines; width = $wdt }
    }
    $s = $global:ADSprites[$name]
    $f = $s.frames
    $frame = $f.idle[$global:AD.CmdCount % $f.idle.Count]
    if ($state -eq 'fail') { $frame = $f.fail }
    elseif ($state -eq 'sleep') { $frame = $f.sleep }
    elseif ($state -eq 'happy') { $frame = $f.happy }
    elseif ($state -eq 'blink') { $frame = $f.blink }
    @{ lines = (AD-RenderPixels -Rows $frame -Palette $s.palette); width = $frame[0].Length }
}

# ── buddy command: roster gallery + gacha roll ──────────────────────────

function global:buddy {
    param([string]$Action)
    $e = $global:AD.Esc
    $dim = "$e[2m"
    $acc = AD-Accent
    if ($Action -eq 'roll') {
        $rng = New-Object System.Random
        $newBuddy = $global:ADBuddyOrder[$rng.Next(0, $global:ADBuddyOrder.Count)]
        $newHat = AD-RollHat $rng
        $global:AD.Config.sprite = $newBuddy
        if ($newHat) { $global:AD.Config.hat = $newHat } else { $global:AD.Config.hat = 'none' }
        AD-PickSprite
        AD-SaveConfig
        Write-Host ""
        if ($newHat) {
            $rar = $global:ADHats[$newHat].rarity
            $rc = $global:ADRarityColors[$rar]
            Write-Host "  you rolled: $acc$newBuddy$e[0m wearing $(AD-Fg $rc[0] $rc[1] $rc[2])$newHat$e[0m $(AD-Fg $rc[0] $rc[1] $rc[2])($rar!)$e[0m"
        } else {
            Write-Host "  you rolled: $acc$newBuddy$e[0m $dim(bare-headed — common)$e[0m"
        }
        $res = AD-BuddyRows -Name $newBuddy -State 'happy'
        $c = $global:ADBuddies[$newBuddy].color
        foreach ($r in $res.rows) { Write-Host "    $(AD-Fg $c[0] $c[1] $c[2])$r$e[0m" }
        Write-Host ""
        Write-Host "  $dim('bedazzle hat daily' to return to the daily draw)$e[0m"
        Write-Host ""
        return
    }
    # gallery, /buddy style
    Write-Host ""
    Write-Host "  $($acc)shell buddies$e[0m $dim(bedazzle sprite <name> to adopt · buddy roll to gamble)$e[0m"
    Write-Host ""
    $perRow = 4
    $cellW = 17
    for ($g = 0; $g -lt $global:ADBuddyOrder.Count; $g += $perRow) {
        $group = $global:ADBuddyOrder[$g..([math]::Min($g + $perRow - 1, $global:ADBuddyOrder.Count - 1))]
        $nameLine = "  "
        foreach ($n in $group) {
            $mark = ""
            if ($n -eq $global:AD.SpriteName) { $mark = " *" }
            $nameLine += "$dim$(($n + $mark).PadRight($cellW))$e[0m"
        }
        Write-Host $nameLine
        for ($r = 0; $r -lt 4; $r++) {
            $line = "  "
            foreach ($n in $group) {
                $b = $global:ADBuddies[$n]
                $c = $b.color
                $line += "$(AD-Fg $c[0] $c[1] $c[2])$($b.rows[$r].PadRight($cellW))$e[0m"
            }
            Write-Host $line
        }
        Write-Host ""
    }
    Write-Host "  $dim`pixel alternates: $(@($global:ADSprites.Keys) -join ', ')$e[0m"
    Write-Host ""
    Write-Host "  $($acc)hats$e[0m $dim(one daily draw per buddy — or 'bedazzle hat <name>' to cheat)$e[0m"
    $hatLine = "  "
    foreach ($hn in @('beanie', 'propeller', 'tophat', 'tinyduck', 'crown', 'wizard', 'halo')) {
        $h = $global:ADHats[$hn]
        $rc = $global:ADRarityColors[$h.rarity]
        $hatLine += "$(AD-Fg $rc[0] $rc[1] $rc[2])$($h.art)$e[0m$dim $hn  $e[0m"
    }
    Write-Host $hatLine
    Write-Host ""
    $rarLine = "  "
    foreach ($pair in @(@('common', '60%'), @('uncommon', '25%'), @('rare', '10%'), @('epic', '4%'), @('legendary', '1%'))) {
        $rc = $global:ADRarityColors[$pair[0]]
        $rarLine += "$(AD-Fg $rc[0] $rc[1] $rc[2])■ $($pair[0]) $($pair[1])$e[0m  "
    }
    Write-Host $rarLine
    $cur = AD-CurrentHatName
    $curTxt = "bare-headed"
    if ($cur) { $curTxt = "wearing $cur" }
    Write-Host ""
    Write-Host "  $dim`today: $($global:AD.SpriteName), $curTxt$e[0m"
    Write-Host ""
}

# ── fetch: pixel planet logo (generated, not hand-drawn) ────────────────

function global:AD-Logo {
    if ($global:AD.LogoLines) { return $global:AD.LogoLines }
    $W = 23; $H = 14
    $cx = 11.0; $cy = 6.5; $r = 5.2
    $hue = $global:AD.Config.accent
    $c1 = AD-HsvToRgb $hue 0.30 1.00
    $c2 = AD-HsvToRgb $hue 0.55 0.95
    $c3 = AD-HsvToRgb $hue 0.70 0.72
    $c4 = AD-HsvToRgb $hue 0.80 0.45
    $ring1 = AD-HsvToRgb ($hue + 55) 0.55 1.00
    $ring2 = AD-HsvToRgb ($hue + 55) 0.65 0.65
    $grid = @()
    for ($y = 0; $y -lt $H; $y++) {
        $row = New-Object object[] $W
        for ($x = 0; $x -lt $W; $x++) {
            $dx = ($x - $cx) * 0.92; $dy = $y - $cy
            $inPlanet = ($dx * $dx + $dy * $dy) -le ($r * $r)
            $ex = ($x - $cx) / 10.5; $ey = ($y - $cy + ($x - $cx) * 0.18) / 2.1
            $ringV = $ex * $ex + $ey * $ey
            $onRing = [math]::Abs($ringV - 1.0) -lt 0.22
            $ringFront = $y -gt ($cy - ($x - $cx) * 0.18)
            $px = $null
            if ($inPlanet) {
                $lx = ($dx / $r + 0.55); $ly = ($dy / $r + 0.55)
                $d = [math]::Sqrt($lx * $lx + $ly * $ly)
                if ($d -lt 0.55) { $px = $c1 }
                elseif ($d -lt 0.95) { $px = $c2 }
                elseif ($d -lt 1.35) { $px = $c3 }
                else { $px = $c4 }
            }
            if ($onRing -and (-not $inPlanet -or $ringFront)) {
                if ($ringV -lt 1.0) { $px = $ring2 } else { $px = $ring1 }
            }
            if ($null -eq $px -and (($x * 7 + $y * 13) % 41) -eq 0) { $px = @(90, 95, 120) }
            $row[$x] = $px
        }
        $grid += , $row
    }
    $e = $global:AD.Esc
    $lines = @()
    for ($y = 0; $y -lt $H; $y += 2) {
        $sb = New-Object System.Text.StringBuilder
        for ($x = 0; $x -lt $W; $x++) {
            $t = $grid[$y][$x]
            if ($y + 1 -lt $H) { $b = $grid[$y + 1][$x] } else { $b = $null }
            if ($null -eq $t -and $null -eq $b) { [void]$sb.Append("$e[0m ") }
            elseif ($null -eq $b) { [void]$sb.Append("$e[0m$e[38;2;$($t[0]);$($t[1]);$($t[2])m▀") }
            elseif ($null -eq $t) { [void]$sb.Append("$e[0m$e[38;2;$($b[0]);$($b[1]);$($b[2])m▄") }
            else { [void]$sb.Append("$e[38;2;$($t[0]);$($t[1]);$($t[2]);48;2;$($b[0]);$($b[1]);$($b[2])m▀") }
        }
        [void]$sb.Append("$e[0m")
        $lines += $sb.ToString()
    }
    $global:AD.LogoLines = $lines
    $lines
}

# ── system info ─────────────────────────────────────────────────────────

function global:AD-Static {
    if ($global:AD.Static) { return $global:AD.Static }
    $path = Join-Path $global:AD.Root 'bedazzle.cache.json'
    if (Test-Path $path) {
        try { $global:AD.Static = Get-Content $path -Raw | ConvertFrom-Json } catch { }
        if ($global:AD.Static) { return $global:AD.Static }
    }
    $os = Get-CimInstance Win32_OperatingSystem
    $cpu = (Get-CimInstance Win32_Processor | Select-Object -First 1).Name -replace '\s+', ' '
    $gpuInst = Get-CimInstance Win32_VideoController | Select-Object -First 1
    $cs = Get-CimInstance Win32_ComputerSystem
    $res = ""
    if ($gpuInst.CurrentHorizontalResolution) { $res = "$($gpuInst.CurrentHorizontalResolution)x$($gpuInst.CurrentVerticalResolution)" }
    $obj = [pscustomobject]@{
        OS      = $os.Caption.Trim()
        Build   = [string]$os.Version
        CPU     = $cpu.Trim()
        GPU     = $gpuInst.Name
        Model   = "$($cs.Manufacturer) $($cs.Model)".Trim()
        Res     = $res
        TotalGB = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
    }
    try { $obj | ConvertTo-Json | Set-Content $path -Encoding UTF8 } catch { }
    $global:AD.Static = $obj
    $obj
}

function global:AD-Bar {
    param([double]$Frac, [int]$Width = 12)
    $e = $global:AD.Esc
    $Frac = [math]::Max(0, [math]::Min(1, $Frac))
    $fill = [int][math]::Round($Frac * $Width)
    if ($Frac -lt 0.7) { $col = AD-Fg 126 231 135 }
    elseif ($Frac -lt 0.85) { $col = AD-Fg 255 223 92 }
    else { $col = AD-Fg 248 81 73 }
    "$col$('█' * $fill)$e[38;2;70;74;90m$('░' * ($Width - $fill))$e[0m"
}

function global:AD-Weather {
    $wf = Join-Path $global:AD.Root 'bedazzle.weather.txt'
    if (Test-Path $wf) {
        $age = ((Get-Date) - (Get-Item $wf).LastWriteTime).TotalMinutes
        if ($age -lt 120) {
            try { return ([IO.File]::ReadAllText($wf)).Trim() } catch { }
        }
    }
    return $null
}

function global:AD-RefreshWeather {
    $wf = Join-Path $global:AD.Root 'bedazzle.weather.txt'
    $stale = $true
    if (Test-Path $wf) { $stale = ((Get-Date) - (Get-Item $wf).LastWriteTime).TotalMinutes -gt 30 }
    if ($stale) {
        try {
            Start-Job -Name ADWeather -ScriptBlock {
                param($p)
                try {
                    $r = Invoke-RestMethod -Uri 'https://wttr.in/?format=%t+%C' -TimeoutSec 10
                    [IO.File]::WriteAllText($p, ([string]$r).Trim())
                } catch { }
            } -ArgumentList $wf | Out-Null
        } catch { }
    }
}

function global:AD-Battery {
    if ($global:AD.BatteryDead) { return $null }
    if (((Get-Date) - $global:AD.BatteryTs).TotalSeconds -lt 60) { return $global:AD.BatteryVal }
    $global:AD.BatteryTs = Get-Date
    try {
        $b = Get-CimInstance Win32_Battery -ErrorAction Stop | Select-Object -First 1
        if ($b) { $global:AD.BatteryVal = [int]$b.EstimatedChargeRemaining }
        else { $global:AD.BatteryDead = $true; $global:AD.BatteryVal = $null }
    } catch { $global:AD.BatteryDead = $true; $global:AD.BatteryVal = $null }
    $global:AD.BatteryVal
}

function global:fetch {
    $e = $global:AD.Esc
    $acc = AD-Accent
    $dim = "$e[2m"
    $st = AD-Static
    $os = Get-CimInstance Win32_OperatingSystem
    $up = (Get-Date) - $os.LastBootUpTime
    $upTxt = ""
    if ($up.Days -gt 0) { $upTxt += "$($up.Days)d " }
    $upTxt += "$($up.Hours)h $($up.Minutes)m"
    $usedGB = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / 1MB, 1)
    $totGB = $st.TotalGB
    $drive = Get-PSDrive C
    $dUsed = [math]::Round($drive.Used / 1GB)
    $dTot = [math]::Round(($drive.Used + $drive.Free) / 1GB)
    $term = "conhost"
    if ($env:WT_SESSION) { $term = "Windows Terminal" }
    $ip = ""
    try {
        $ip = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
            Where-Object { $_.IPAddress -notlike '169.*' -and $_.IPAddress -ne '127.0.0.1' } |
            Select-Object -First 1).IPAddress
    } catch { }
    $user = "$acc$env:USERNAME$e[0m$dim@$e[0m$acc$env:COMPUTERNAME$e[0m"

    $rows = @()
    $rows += , @('', $user)
    $rows += , @('', "$dim$('─' * ($env:USERNAME.Length + $env:COMPUTERNAME.Length + 1))$e[0m")
    $rows += , @('os', $st.OS -replace 'Microsoft ', '')
    $rows += , @('kernel', $st.Build)
    $rows += , @('uptime', $upTxt)
    $rows += , @('shell', "PowerShell $($PSVersionTable.PSVersion)")
    $rows += , @('term', $term)
    $rows += , @('host', $st.Model)
    $rows += , @('cpu', $st.CPU)
    $rows += , @('gpu', $st.GPU)
    if ($st.Res) { $rows += , @('display', $st.Res) }
    $rows += , @('memory', "$(AD-Bar ($usedGB / $totGB))  $usedGB / $totGB GiB")
    $rows += , @('disk', "$(AD-Bar ($dUsed / [math]::Max(1,$dTot)))  $dUsed / $dTot GB")
    if ($ip) { $rows += , @('ip', $ip) }
    if (AD-On 'weather') { $w = AD-Weather; if ($w) { $rows += , @('weather', $w) } }
    $bat = $null
    if (AD-On 'battery') { $bat = AD-Battery }
    if ($null -ne $bat) { $rows += , @('battery', "$bat%") }
    $pal1 = ""; $pal2 = ""
    foreach ($i in 40..47) { $pal1 += "$e[${i}m   " }
    foreach ($i in 100..107) { $pal2 += "$e[${i}m   " }
    $rows += , @('', '')
    $rows += , @('', "$pal1$e[0m")
    $rows += , @('', "$pal2$e[0m")

    $logo = AD-Logo
    $n = [math]::Max($logo.Count, $rows.Count)
    Write-Host ""
    for ($i = 0; $i -lt $n; $i++) {
        $l = ""
        if ($i -lt $logo.Count) { $l = $logo[$i] } else { $l = " " * 23 }
        $r = ""
        if ($i -lt $rows.Count) {
            $k = $rows[$i][0]; $v = $rows[$i][1]
            if ($k) { $r = "$acc$($k.PadRight(9))$e[0m$v" } else { $r = $v }
        }
        Write-Host ("  $l  $r")
    }
    Write-Host ""
}

# ── git ─────────────────────────────────────────────────────────────────

function global:AD-GitInfo {
    $loc = Get-Location
    if ($loc.Provider.Name -ne 'FileSystem') { return $null }
    $d = $loc.ProviderPath
    while ($d) {
        $gitDir = Join-Path $d '.git'
        if (Test-Path -LiteralPath (Join-Path $gitDir 'HEAD')) {
            $branch = $null
            try {
                $line = [IO.File]::ReadAllLines((Join-Path $gitDir 'HEAD'))[0]
                if ($line -match 'ref: refs/heads/(.+)') { $branch = $Matches[1] }
                elseif ($line.Length -ge 7) { $branch = $line.Substring(0, 7) }
            } catch { }
            if (-not $branch) { return $null }
            $state = ""
            if (Test-Path -LiteralPath (Join-Path $gitDir 'MERGE_HEAD')) { $state = "merge" }
            elseif ((Test-Path -LiteralPath (Join-Path $gitDir 'rebase-merge')) -or
                    (Test-Path -LiteralPath (Join-Path $gitDir 'rebase-apply'))) { $state = "rebase" }
            return @{ branch = $branch; state = $state }
        }
        $parent = Split-Path $d -Parent
        if (-not $parent -or $parent -eq $d) { break }
        $d = $parent
    }
    return $null
}

# ── spirits (legacy, off by default) ────────────────────────────────────

$global:ADSpirits = @(
    '( ⚆ _ ⚆ )  the shell noticed you noticing it',
    '◉_◉  every process dreams of being PID 1',
    'ʕ•ᴥ•ʔ  your last command was seen and appreciated',
    '(¬‿¬)  i read your command history. bold choices'
)

# ── lava: metaballs lamp in the corner, background process ──────────────

function global:AD-LavaPidFile { Join-Path $global:AD.Root 'bedazzle.lava.pid' }

function global:AD-LavaRunning {
    $pf = AD-LavaPidFile
    if (-not (Test-Path $pf)) { return $false }
    try {
        $procId = [int](Get-Content $pf -TotalCount 1)
        $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
        return ($null -ne $p -and $p.ProcessName -like 'python*')
    } catch { return $false }
}

function global:lava {
    param([string]$Action)
    $e = $global:AD.Esc
    $pf = AD-LavaPidFile
    $running = AD-LavaRunning
    $stop = ($Action -eq 'off') -or ($running -and $Action -ne 'on')
    if ($stop) {
        if ($running) {
            try { Stop-Process -Id ([int](Get-Content $pf -TotalCount 1)) -Force -ErrorAction SilentlyContinue } catch { }
            Write-Host " lava: off"
        } else { Write-Host " lava: not running" }
        Remove-Item $pf -Force -ErrorAction SilentlyContinue
        return
    }
    if ($running) { Write-Host " lava: already flowing"; return }
    $py = Join-Path $global:AD.Root '.venv\Scripts\python.exe'
    $p = Start-Process -FilePath $py -ArgumentList @("$($global:AD.Root)\bgfx.py", '--pidfile', $pf) -NoNewWindow -PassThru
    Set-Content -Path $pf -Value $p.Id
    Write-Host " lava: on $($global:AD.Esc)[2m(metaballs in the corner — 'lava' again to stop)$($global:AD.Esc)[0m"
}

# ── the prompt ──────────────────────────────────────────────────────────

function global:prompt {
    $ok = $?
    $e = $global:AD.Esc
    $global:AD.CmdCount++
    if (-not $ok) { $global:AD.Stats.Fails++ }
    if ($global:ADPromptHook) { try { & $global:ADPromptHook } catch { } }
    $w = 80
    try { $w = $Host.UI.RawUI.WindowSize.Width } catch { }
    if (-not $w -or $w -lt 30) { $w = 80 }
    $dim = "$e[2m"
    $acc = AD-Accent

    # last command duration + idle time (both feed buddy mood + right info)
    $msVal = 0.0
    $h = Get-History -Count 1 -ErrorAction SilentlyContinue
    if ($h -and $h.EndExecutionTime -gt $h.StartExecutionTime) {
        $msVal = ($h.EndExecutionTime - $h.StartExecutionTime).TotalMilliseconds
        $global:AD.Durations.Add($msVal)
        if ($global:AD.Durations.Count -gt 40) { $global:AD.Durations.RemoveAt(0) }
    }
    $idleSec = 0.0
    $now = Get-Date
    if ($global:AD.LastPrompt) {
        $idleSec = ($now - $global:AD.LastPrompt).TotalSeconds - ($msVal / 1000.0)
    }
    $global:AD.LastPrompt = $now

    # feed the termbg daemon (one cheap append; only when it's running)
    if (Test-Path (Join-Path $global:AD.Root 'termbg.pid')) {
        try {
            $st = 'ok'; if (-not $ok) { $st = 'fail' }
            [IO.File]::AppendAllText((Join-Path $global:AD.Root 'termbg.events'),
                "$st|$($global:AD.CmdCount)|$((Get-Location).Path)`n")
        } catch { }
    }
    # feed the pinned pet (pet.py) when it's running
    $petOn = Test-Path (Join-Path $global:AD.Root 'bedazzle.pet.pid')
    if ($petOn) {
        try {
            $hatCur = AD-CurrentHatName; if (-not $hatCur) { $hatCur = '' }
            $okj = 'false'; if ($ok) { $okj = 'true' }
            $ts = [DateTimeOffset]::Now.ToUnixTimeSeconds()
            [IO.File]::WriteAllText((Join-Path $global:AD.Root 'pet.json'),
                ('{"ok":' + $okj + ',"ms":' + [int]$msVal + ',"count":' + $global:AD.CmdCount +
                 ',"ts":' + $ts + ',"sprite":"' + $global:AD.SpriteName + '","hat":"' + $hatCur + '"}'))
        } catch { }
    }

    if ((AD-On 'spirits') -and (Get-Random -Maximum 22) -eq 0) {
        Write-Host "$dim $($global:ADSpirits | Get-Random)$e[0m"
    }
    if (AD-On 'rule') {
        Write-Host "$(AD-Rule ($w - 2) (($global:AD.CmdCount * 14) % 360))"
    }

    # left segment: path (+git, +venv)
    $path = (Get-Location).Path
    if ($HOME -and $path.StartsWith($HOME)) { $path = '~' + $path.Substring($HOME.Length) }
    if ((AD-On 'shortpath')) {
        $segs = $path -split '\\'
        if ($segs.Count -gt 3) {
            $head = $segs[0]
            $mid = @()
            for ($i = 1; $i -lt $segs.Count - 1; $i++) {
                if ($segs[$i].Length -gt 0) { $mid += $segs[$i].Substring(0, 1) } else { $mid += '' }
            }
            $path = (@($head) + $mid + @($segs[-1])) -join '\'
        }
    }
    $left = "$acc$e[1m$path$e[0m"
    $leftPlain = $path
    if (AD-On 'git') {
        $gi = AD-GitInfo
        if ($gi) {
            $btxt = $gi.branch
            if ($gi.state) { $btxt += " $($gi.state)!" }
            $left += "  $(AD-Accent2)⎇ $btxt$e[0m"
            $leftPlain += "  x " + $btxt
        }
    }
    if ((AD-On 'venv') -and $env:VIRTUAL_ENV) {
        $vn = Split-Path $env:VIRTUAL_ENV -Leaf
        if ($vn -match '^\.?venv$') {
            # generic name -> show which project's venv this actually is
            $vn = "$(Split-Path (Split-Path $env:VIRTUAL_ENV -Parent) -Leaf)\$vn"
        }
        $left += "  $(AD-Fg 126 231 135)⚡$vn$e[0m"
        $leftPlain += "  x" + $vn
    }

    # right segment: duration · status · clock · battery · weather
    $right = ""; $rightPlain = ""
    if (AD-On 'rightinfo') {
        $parts = @(); $plainParts = @()
        if ($msVal -ge 1) {
            $durText = $null
            if ($msVal -ge 60000) { $durText = "{0:n1}m" -f ($msVal / 60000) }
            elseif ($msVal -ge 1000) { $durText = "{0:n2}s" -f ($msVal / 1000) }
            else { $durText = "{0:n0}ms" -f $msVal }
            $parts += "$dim$durText$e[0m"; $plainParts += $durText
        }
        if ($ok) { $parts += "$(AD-Fg 126 231 135)✓$e[0m"; $plainParts += "x" }
        else { $parts += "$(AD-Fg 248 81 73)✗$e[0m"; $plainParts += "x" }
        $clock = (Get-Date).ToString('HH:mm')
        $parts += "$dim$clock$e[0m"; $plainParts += $clock
        if (AD-On 'battery') {
            $bat = AD-Battery
            if ($null -ne $bat) {
                if ($bat -le 20) { $bc = AD-Fg 248 81 73 } else { $bc = $dim }
                $parts += "$bc$bat%$e[0m"; $plainParts += "$bat%"
            }
        }
        if (AD-On 'weather') {
            $wx = AD-Weather
            if ($wx) {
                $temp = ($wx -split ' ')[0]
                $parts += "$dim$temp$e[0m"; $plainParts += $temp
            }
        }
        $right = $parts -join "$dim · $e[0m"
        $rightPlain = $plainParts -join " · "
    }

    # buddy: rows above the info line, last row on it
    # (suppressed while the pinned pet daemon owns the corner)
    $spriteOn = (AD-On 'sprite') -and -not $petOn
    $spr = $null; $sprCol = $w + 1
    if ($spriteOn) {
        $spr = AD-SpriteInfo -Ok $ok -Ms $msVal -IdleSec $idleSec
        $sprCol = [math]::Max(2, $w - $spr.width - 1)
        for ($i = 0; $i -lt $spr.lines.Count - 1; $i++) {
            Write-Host "$e[0m$e[${sprCol}G$($spr.lines[$i])"
        }
    } elseif (AD-On 'airy') {
        Write-Host ""
    }
    $line = $left
    if ($right) {
        $rightEnd = $w
        if ($spriteOn) { $rightEnd = $sprCol - 2 }
        $col = $rightEnd - $rightPlain.Length
        if ($col -gt ($leftPlain.Length + 4)) { $line += "$e[${col}G$right" }
    }
    if ($spriteOn) { $line += "$e[${sprCol}G$($spr.lines[-1])" }
    Write-Host $line

    if (AD-On 'title') {
        try { $Host.UI.RawUI.WindowTitle = "$path" } catch { }
    }
    if ($ok) { $arrow = "$acc❯$e[0m" } else { $arrow = "$(AD-Fg 248 81 73)❯$e[0m" }
    return "$arrow "
}

# ── bedazzle control command ────────────────────────────────────────────

function global:bedazzle {
    param([string]$Action, [string]$Name)
    $e = $global:AD.Esc
    $dim = "$e[2m"
    $acc = AD-Accent
    $feats = $global:AD.Config.features
    $desc = @{
        fetch = 'system panel on startup'; sprite = 'buddy in the prompt corner'
        rightinfo = 'duration/status/clock right side'; git = 'branch + merge state'
        venv = 'python venv chip'; shortpath = 'fish-style path compression'
        title = 'tab title follows folder'; airy = 'breathing room above prompt'
        battery = 'battery %% when present'; weather = 'cached wttr.in temperature'
        spirits = 'kaomoji visitors (v1)'; rule = 'gradient rule line (v1)'
    }
    switch ($Action) {
        { $_ -in 'on', 'off' } {
            if (-not $feats.ContainsKey($Name)) {
                Write-Host "$dim unknown feature '$Name' — try plain 'bedazzle'$e[0m"; return
            }
            $feats[$Name] = ($Action -eq 'on')
            AD-SaveConfig
            Write-Host " $acc$Name$e[0m -> $Action"
            return
        }
        'sprite' {
            $all = @($global:ADBuddyOrder) + @($global:ADSprites.Keys) + @('random')
            if ($all -contains $Name) {
                $global:AD.Config.sprite = $Name; AD-PickSprite; AD-SaveConfig
                Write-Host " buddy -> $acc$($global:AD.SpriteName)$e[0m"
            } else {
                Write-Host " buddies: $($global:ADBuddyOrder -join ', ')"
                Write-Host " pixel:   $(@($global:ADSprites.Keys) -join ', '), random"
            }
            return
        }
        'hat' {
            $valid = @($global:ADHats.Keys) + @('daily', 'none')
            if ($valid -contains $Name) {
                $global:AD.Config.hat = $Name; AD-SaveConfig
                $cur = AD-CurrentHatName
                $curTxt = 'bare-headed'
                if ($cur) { $curTxt = $cur }
                Write-Host " hat -> $acc$Name$e[0m $dim(today: $curTxt)$e[0m"
            } else {
                Write-Host " hats: $(@($global:ADHats.Keys) -join ', '), daily, none"
            }
            return
        }
        'accent' {
            $names = @{ blue = 215; violet = 270; green = 140; amber = 45; red = 2; cyan = 185; pink = 330 }
            $hue = $null
            if ($names.ContainsKey($Name)) { $hue = $names[$Name] }
            else { try { $hue = [double]$Name } catch { } }
            if ($null -ne $hue) {
                $global:AD.Config.accent = $hue
                $global:AD.LogoLines = $null
                AD-SaveConfig
                Write-Host " accent -> $(AD-Accent)$hue$e[0m  $(AD-Accent)██$(AD-Accent2)██$e[0m"
            } else {
                Write-Host " accent: $($names.Keys -join ', '), or any hue 0-360"
            }
            return
        }
        'stats' {
            $up = (Get-Date) - $global:AD.Stats.Start
            $sess = "{0:n0}m" -f $up.TotalMinutes
            Write-Host ""
            Write-Host "  $($acc)session$e[0m   $sess"
            Write-Host "  $($acc)commands$e[0m  $($global:AD.CmdCount)"
            Write-Host "  $($acc)failed$e[0m    $($global:AD.Stats.Fails)"
            if ($global:AD.Durations.Count -gt 1) {
                $sparks = '▁▂▃▄▅▆▇█'
                $ds = $global:AD.Durations | Select-Object -Last 30
                $mx = [math]::Max(1.0, ($ds | Measure-Object -Maximum).Maximum)
                $line = ""
                foreach ($d in $ds) {
                    $i = [int][math]::Min(7, [math]::Floor(($d / $mx) * 7.999))
                    $line += $sparks[$i]
                }
                $avg = ($ds | Measure-Object -Average).Average
                Write-Host "  $($acc)durations$e[0m $(AD-Accent2)$line$e[0m  $dim(avg $("{0:n0}ms" -f $avg), max $("{0:n0}ms" -f $mx))$e[0m"
            }
            Write-Host ""
            return
        }
        default {
            Write-Host ""
            Write-Host "  $($acc)$e[1mbedazzle$e[0m $dim— every addon, individually togglable$e[0m"
            Write-Host ""
            foreach ($k in ($feats.Keys | Sort-Object)) {
                if ($feats[$k]) { $state = "$(AD-Fg 126 231 135) on$e[0m " } else { $state = "$dim off$e[0m" }
                Write-Host ("   {0} {1}{2}{3} {4}{5}{6}" -f $state, $acc, $k.PadRight(10), "$e[0m", $dim, $desc[$k], "$e[0m")
            }
            Write-Host ""
            Write-Host "  $dim bedazzle on|off <name>      toggle a feature$e[0m"
            Write-Host "  $dim bedazzle sprite <name>      pick your buddy ('buddy' shows the roster)$e[0m"
            Write-Host "  $dim bedazzle hat <name>         daily · none · or a specific hat$e[0m"
            Write-Host "  $dim bedazzle accent <name|hue>  blue · violet · green · amber · red · cyan · pink$e[0m"
            Write-Host "  $dim bedazzle stats              session stats + duration sparkline$e[0m"
            Write-Host "  $dim buddy [roll]                pet roster · gacha roll$e[0m"
            Write-Host "  $dim pet                         pin ONE live buddy top-right (no duplicates)$e[0m"
            Write-Host "  $dim termbg                      living background — run it alone for full help$e[0m"
            Write-Host "  $dim fetch · lava · wall · hr    system panel · corner lamp · one-shot bg · divider$e[0m"
            Write-Host ""
        }
    }
}

# ── launchers + utilities ───────────────────────────────────────────────

function global:hr {
    $w = 80
    try { $w = $Host.UI.RawUI.WindowSize.Width } catch { }
    Write-Host (AD-Rule ($w - 1) (Get-Random -Maximum 360))
}
function global:AD-TermbgRunning {
    $pf = Join-Path $global:AD.Root 'termbg.pid'
    if (-not (Test-Path $pf)) { return $false }
    try {
        $procId = [int](Get-Content $pf -TotalCount 1)
        $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
        return ($null -ne $p -and $p.ProcessName -like 'python*')
    } catch { return $false }
}

function global:AD-TermbgKill {
    # kill by command line: the pidfile only knows the venv launcher shim,
    # not the real pythonw underneath, and orphans survive tab closes
    try {
        Get-CimInstance Win32_Process -Filter "Name like 'python%'" -ErrorAction Stop |
            Where-Object { $_.CommandLine -match 'termbg\.py.{0,40}daemon' } |
            ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    } catch { }
}

function global:termbg {
    param([string]$Action, [string]$Name)
    $root = $global:AD.Root
    $e = $global:AD.Esc
    $py = Join-Path $root '.venv\Scripts\python.exe'
    $pyw = Join-Path $root '.venv\Scripts\pythonw.exe'
    if (-not (Test-Path $pyw)) { $pyw = $py }
    $pf = Join-Path $root 'termbg.pid'
    switch ($Action) {
        'on' {
            AD-TermbgKill   # a clean slate: exactly one daemon, current code
            Remove-Item $pf -Force -ErrorAction SilentlyContinue
            & $py "$root\termbg.py" once
            $p = Start-Process -FilePath $pyw -ArgumentList @("$root\termbg.py", 'daemon', '--pidfile', $pf) -PassThru -WindowStyle Hidden
            Set-Content -Path $pf -Value $p.Id
            Write-Host " termbg: on $e[2m(the background now evolves with each command — 'termbg' for options)$e[0m"
            return
        }
        'freeze' {
            if (-not (AD-TermbgRunning)) { Write-Host ' termbg: nothing running to freeze'; return }
            AD-TermbgKill
            Remove-Item $pf -Force -ErrorAction SilentlyContinue
            Write-Host " termbg: frozen $e[2m— the current image stays put ('termbg on' resumes, 'termbg off' removes)$e[0m"
            return
        }
        'off' {
            AD-TermbgKill
            Remove-Item $pf -Force -ErrorAction SilentlyContinue
            & $py "$root\termbg.py" off
            return
        }
        { $_ -in 'use', 'palette', 'overlay', 'opacity' } { & $py "$root\termbg.py" $Action $Name; return }
        'once' { & $py "$root\termbg.py" once; return }
        default {
            $run = '0'; if (AD-TermbgRunning) { $run = '1' }
            & $py "$root\termbg.py" status --running $run
        }
    }
}

function global:pet {
    param([string]$Action)
    $root = $global:AD.Root
    $e = $global:AD.Esc
    $pf = Join-Path $root 'bedazzle.pet.pid'
    $running = $false
    if (Test-Path $pf) {
        try {
            $procId = [int](Get-Content $pf -TotalCount 1)
            $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
            $running = ($null -ne $p -and $p.ProcessName -like 'python*')
        } catch { }
    }
    $stop = ($Action -eq 'off') -or ($running -and $Action -ne 'on')
    if ($stop) {
        if ($running) {
            try { Stop-Process -Id ([int](Get-Content $pf -TotalCount 1)) -Force -ErrorAction SilentlyContinue } catch { }
            Write-Host " pet: off $e[2m(the inline prompt buddy returns)$e[0m"
        } else { Write-Host ' pet: not running' }
        Remove-Item $pf -Force -ErrorAction SilentlyContinue
        return
    }
    if ($running) { Write-Host ' pet: already pinned'; return }
    # seed pet.json so the pet knows who it is before the first prompt
    try {
        $hatCur = AD-CurrentHatName; if (-not $hatCur) { $hatCur = '' }
        $ts = [DateTimeOffset]::Now.ToUnixTimeSeconds()
        [IO.File]::WriteAllText((Join-Path $root 'pet.json'),
            ('{"ok":true,"ms":0,"count":' + $global:AD.CmdCount + ',"ts":' + $ts +
             ',"sprite":"' + $global:AD.SpriteName + '","hat":"' + $hatCur + '"}'))
    } catch { }
    $py = Join-Path $root '.venv\Scripts\python.exe'
    $p = Start-Process -FilePath $py -ArgumentList @("$root\pet.py", '--pidfile', $pf) -NoNewWindow -PassThru
    Set-Content -Path $pf -Value $p.Id
    Write-Host " pet: pinned top-right $e[2m(one $($global:AD.SpriteName), zero duplicates — 'pet' again to unpin)$e[0m"
}

# wall = the old one-shot: paint one fresh frame, no daemon
function global:wall {
    param([string]$Action)
    if ($Action -eq 'off') { termbg off } else { termbg once }
}

# ── startup ─────────────────────────────────────────────────────────────

# venv Activate.ps1 would prepend "(.venv) " to the prompt — the ⚡ chip
# already covers it
$env:VIRTUAL_ENV_DISABLE_PROMPT = '1'

$global:AD.Config = AD-LoadConfig
AD-ComputeDailyHat
AD-PickSprite
if ($Host.Name -match 'ConsoleHost') {
    if (AD-On 'weather') { AD-RefreshWeather }
    if (AD-On 'fetch') { fetch }
}
