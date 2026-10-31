param([string]$OutputDirectory = (Join-Path $PSScriptRoot ''))
Add-Type -AssemblyName System.Drawing
$ErrorActionPreference='Stop'
$W=1440; $H=900
$root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$art=Join-Path $root 'frontend\public\art\adventure'
$null=New-Item -ItemType Directory -Force -Path $OutputDirectory
$ink=[System.Drawing.ColorTranslator]::FromHtml('#202737'); $muted=[System.Drawing.ColorTranslator]::FromHtml('#687385'); $blue=[System.Drawing.ColorTranslator]::FromHtml('#1758D4'); $pale=[System.Drawing.ColorTranslator]::FromHtml('#EAF1FF'); $line=[System.Drawing.ColorTranslator]::FromHtml('#E9E5DE'); $paper=[System.Drawing.ColorTranslator]::FromHtml('#FFFDF8'); $canvas=[System.Drawing.ColorTranslator]::FromHtml('#F7F4EE'); $green=[System.Drawing.ColorTranslator]::FromHtml('#3D8A69')
function New-Canvas { $b=New-Object System.Drawing.Bitmap($W,$H); $g=[System.Drawing.Graphics]::FromImage($b); $g.SmoothingMode='AntiAlias'; $g.InterpolationMode='HighQualityBicubic'; $g.TextRenderingHint='AntiAliasGridFit'; $g.Clear($canvas); return @($b,$g) }
function Brush($c){ New-Object System.Drawing.SolidBrush($c) }
function Font($size,$bold=$false){ $style=[System.Drawing.FontStyle]::Regular; if($bold){$style=[System.Drawing.FontStyle]::Bold}; New-Object System.Drawing.Font('Segoe UI',$size,$style,[System.Drawing.GraphicsUnit]::Pixel) }
function Txt($g,[string]$s,[float]$x,[float]$y,[float]$size=16,$color=$ink,$bold=$false){$b=Brush $color; $g.DrawString($s,(Font $size $bold),$b,$x,$y); $b.Dispose()}
function Round($g,[float]$x,[float]$y,[float]$w,[float]$h,[float]$r,$fill,$stroke=$null){$p=New-Object System.Drawing.Drawing2D.GraphicsPath; $d=2*$r; $p.AddArc($x,$y,$d,$d,180,90);$p.AddArc($x+$w-$d,$y,$d,$d,270,90);$p.AddArc($x+$w-$d,$y+$h-$d,$d,$d,0,90);$p.AddArc($x,$y+$h-$d,$d,$d,90,90);$p.CloseFigure();$b=Brush $fill;$g.FillPath($b,$p);$b.Dispose();if($stroke){$pn=New-Object System.Drawing.Pen($stroke,1);$g.DrawPath($pn,$p);$pn.Dispose()};$p.Dispose()}
function ImageContain($g,$path,[float]$x,[float]$y,[float]$w,[float]$h){$im=[System.Drawing.Image]::FromFile($path);$s=[Math]::Min($w/$im.Width,$h/$im.Height);$dw=$im.Width*$s;$dh=$im.Height*$s;$g.DrawImage($im,[float]($x+($w-$dw)/2),[float]($y+($h-$dh)/2),[float]$dw,[float]$dh);$im.Dispose()}
function ImageCover($g,$path,[float]$x,[float]$y,[float]$w,[float]$h){$im=[System.Drawing.Image]::FromFile($path);$s=[Math]::Max($w/$im.Width,$h/$im.Height);$dw=$im.Width*$s;$dh=$im.Height*$s;$state=$g.Save();$g.SetClip([System.Drawing.RectangleF]::new($x,$y,$w,$h));$g.DrawImage($im,[float]($x+($w-$dw)/2),[float]($y+($h-$dh)/2),[float]$dw,[float]$dh);$g.Restore($state);$im.Dispose()}
function ImageCoverRounded($g,$path,[float]$x,[float]$y,[float]$w,[float]$h,[float]$r){$p=New-Object System.Drawing.Drawing2D.GraphicsPath;$d=2*$r;$p.AddArc($x,$y,$d,$d,180,90);$p.AddArc($x+$w-$d,$y,$d,$d,270,90);$p.AddArc($x+$w-$d,$y+$h-$d,$d,$d,0,90);$p.AddArc($x,$y+$h-$d,$d,$d,90,90);$p.CloseFigure();$state=$g.Save();$g.SetClip($p);ImageCover $g $path $x $y $w $h;$g.Restore($state);$p.Dispose()}
function FadeOverlay($g,[float]$x,[float]$y,[float]$w,[float]$h,$color){for($i=0;$i -lt $w;$i++){ $a=[int](250*(1-($i/[double]$w)));$b=New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb($a,$color.R,$color.G,$color.B));$g.FillRectangle($b,$x+$i,$y,1,$h);$b.Dispose() }}
function Header($g,$active){ Txt $g 'MINYAR' 46 20 22 $ink $true; Txt $g 'Practice worlds' 238 25 15 $blue $true; Txt $g 'Overview' 392 25 15 $muted $false; Txt $g 'Quest' 500 25 15 $muted $false; Round $g 1242 14 152 42 20 $paper $line; Txt $g 'Local profile' 1271 26 13 $muted $false; $g.DrawLine((New-Object System.Drawing.Pen($line,1)),32,68,1408,68) }
function Pill($g,$text,$x,$y,$w,$fill=$pale,$fg=$blue){Round $g $x $y $w 29 14 $fill;$sf=New-Object System.Drawing.StringFormat;$sf.Alignment='Center';$sf.LineAlignment='Center';$b=Brush $fg;$f=Font 12 $true;$rect=[System.Drawing.RectangleF]::new($x,$y,$w,29);$g.DrawString($text,$f,$b,$rect,$sf);$f.Dispose();$sf.Dispose();$b.Dispose()}
function Button($g,$text,$x,$y,$w){Round $g $x $y $w 52 18 $blue;Txt $g $text ($x+22) ($y+15) 16 ([System.Drawing.Color]::White) $true;Txt $g '→' ($x+$w-34) ($y+13) 22 ([System.Drawing.Color]::White) $true}
function Companion($g,$x,$y){Round $g $x $y 68 43 20 ([System.Drawing.Color]::FromArgb(255,34,39,48));$b=Brush ([System.Drawing.Color]::White);$g.FillEllipse($b,$x+14,$y+12,16,16);$g.FillEllipse($b,$x+38,$y+12,16,16);$b.Dispose();$b=Brush ([System.Drawing.Color]::FromArgb(255,34,39,48));$g.FillEllipse($b,$x+19,$y+17,7,7);$g.FillEllipse($b,$x+43,$y+17,7,7);$b.Dispose()}
function Footer($g){Txt $g 'DESIGN CONCEPT · SAMPLE DATA' 42 864 11 $muted $true;Txt $g 'Illustrative layout only · no clinical interpretation' 250 864 11 $muted $false}
function Save($b,$name){$p=Join-Path $OutputDirectory $name;$b.Save($p,[System.Drawing.Imaging.ImageFormat]::Png);$b.Dispose();$p}

# HOME / WELCOME
$c=New-Canvas; $b=$c[0];$g=$c[1];Header $g 'home'
Round $g 38 91 1364 386 26 ([System.Drawing.Color]::FromArgb(255,251,248,241)) $line
# Full scenic hero, softened behind the headline so the illustration and copy read as one scene.
ImageCoverRounded $g (Join-Path $art 'journey-hero.png') 39 92 1362 384 25
FadeOverlay $g 40 92 890 384 ([System.Drawing.Color]::FromArgb(255,251,248,241))
Round $g 38 91 1364 386 26 ([System.Drawing.Color]::Transparent) $line
Pill $g 'A SMALL MOMENT FOR YOU' 72 126 198 ([System.Drawing.Color]::FromArgb(255,255,255,255)) $blue
Txt $g 'A little practice.' 72 184 43 $ink $true;Txt $g 'A wider horizon.' 72 232 43 $ink $true
Txt $g 'Explore five playful worlds, each shaped around' 74 302 17 $muted;Txt $g 'a different way of thinking.' 74 328 17 $muted
Button $g 'Choose a world' 72 369 222
Txt $g 'Every world is open. Start wherever curiosity leads.' 72 438 13 $muted
Txt $g 'YOUR JOURNEY, YOUR PACE' 48 509 12 $muted $true;Txt $g 'Five worlds to explore' 48 533 27 $ink $true;Txt $g 'Pick a landscape and see what kind of challenge lives there.' 48 570 15 $muted
$worlds=@(@('Memory','Notice & remember','world-memory.png'),@('Attention','Find what matters','world-attention.png'),@('Flexibility','Try another path','world-flexibility.png'),@('Reasoning','Connect the clues','world-reasoning.png'),@('Planning','Shape a route','world-planning.png'))
for($i=0;$i -lt 5;$i++){ $x=40+$i*276; Round $g $x 612 260 210 22 $paper $line;ImageContain $g (Join-Path $art $worlds[$i][2]) ($x+15) 620 230 116;Txt $g $worlds[$i][0] ($x+18) 744 19 $ink $true;Txt $g $worlds[$i][1] ($x+18) 774 13 $muted;Txt $g 'Explore world' ($x+18) 795 13 $blue $true;Txt $g '↗' ($x+218) 791 17 $blue $true }
Footer $g;Companion $g 1321 824; Save $b 'home-welcome.png'

# ANALYTICS
$c=New-Canvas;$b=$c[0];$g=$c[1];Header $g 'analytics'
Pill $g 'OVERVIEW' 42 92 90
Txt $g 'A clearer view of your practice' 42 133 33 $ink $true;Txt $g 'Saved task evidence, uncertainty and the next useful step.' 44 177 16 $muted
Round $g 40 220 918 536 20 $paper $line
Txt $g 'Five task dimensions' 66 244 21 $ink $true;Txt $g 'Each estimate belongs to its own task family.' 66 275 14 $muted
# table header
Txt $g 'DIMENSION' 68 319 11 $muted $true;Txt $g 'TASK ESTIMATE' 410 319 11 $muted $true;Txt $g 'UNCERTAINTY' 610 319 11 $muted $true;Txt $g 'EVIDENCE' 791 319 11 $muted $true
$rows=@(@('Memory','Remembering','Developing','Medium','4 saved tasks'),@('Attention','Selective focus','Building','High','2 saved tasks'),@('Flexibility','Rule switching','Developing','Medium','3 saved tasks'),@('Reasoning','Pattern logic','Building','High','2 saved tasks'),@('Planning','Route design','Unassessed','—','No saved tasks'))
for($i=0;$i -lt 5;$i++){ $y=344+$i*75; $g.DrawLine((New-Object System.Drawing.Pen($line,1)),66,$y,930,$y);$asset=@('world-memory.png','world-attention.png','world-flexibility.png','world-reasoning.png','world-planning.png')[$i];ImageContain $g (Join-Path $art $asset) 68 ($y+10) 55 52;Txt $g $rows[$i][0] 132 ($y+13) 16 $ink $true;Txt $g $rows[$i][1] 132 ($y+36) 12 $muted;Txt $g $rows[$i][2] 410 ($y+19) 15 $ink $true;Txt $g 'Task-specific' 410 ($y+42) 12 $muted;Pill $g $rows[$i][3] 610 ($y+18) 84 ([System.Drawing.Color]::FromArgb(255,244,241,232)) $muted;Txt $g $rows[$i][4] 791 ($y+23) 13 $muted }
$g.DrawLine((New-Object System.Drawing.Pen($line,1)),66,719,930,719);Txt $g 'Estimates are descriptive task summaries, not a clinical diagnosis.' 68 728 12 $muted
Round $g 986 220 414 257 20 $paper $line;Txt $g 'Evidence coverage' 1014 245 19 $ink $true;Txt $g 'Saved, scored task attempts' 1014 276 13 $muted
# ring graphic
$pn=New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(255,230,236,245),12);$g.DrawEllipse($pn,1020,319,92,92);$pn.Dispose();$pn=New-Object System.Drawing.Pen($blue,12);$pn.StartCap='Round';$pn.EndCap='Round';$g.DrawArc($pn,1020,319,92,92,-90,232);$pn.Dispose();Txt $g '68%' 1038 350 20 $ink $true
Txt $g '11 of 16 example attempts' 1138 332 15 $ink $true;Txt $g 'have linked evidence records.' 1138 356 13 $muted;Txt $g 'Coverage is shown for context; it does not' 1014 431 12 $muted;Txt $g 'increase or decrease an estimate by itself.' 1014 451 12 $muted
Round $g 986 493 414 263 20 $paper $line;Txt $g 'Recent saved history' 1014 518 19 $ink $true;Txt $g 'Synthetic examples · illustrative only' 1014 547 12 $muted
$hist=@(@('Oct 16','Memory · paired recall','Evidence linked'),@('Oct 14','Attention · target search','Evidence linked'),@('Oct 11','Reasoning · pattern set','Evidence linked'))
for($i=0;$i -lt 3;$i++){ $y=581+$i*48; if($i -gt 0){$g.DrawLine((New-Object System.Drawing.Pen($line,1)),1014,$y,1372,$y)}; Txt $g $hist[$i][0] 1015 ($y+10) 12 $muted;Txt $g $hist[$i][1] 1080 ($y+8) 13 $ink $true;Txt $g $hist[$i][2] 1080 ($y+27) 11 $green }
Round $g 986 773 414 65 18 $pale;Txt $g 'NEXT STEP' 1006 784 10 $blue $true;Txt $g 'Try one short Planning task' 1006 802 14 $ink $true;Txt $g '→' 1360 792 23 $blue $true
Footer $g;Companion $g 1321 844; Save $b 'overview-analytics.png'

# QUEST
$c=New-Canvas;$b=$c[0];$g=$c[1];Header $g 'quest'
Pill $g 'QUEST' 42 92 76
Txt $g 'Your path through the worlds' 42 133 33 $ink $true;Txt $g 'Synthetic activity examples · all five branches stay open.' 44 177 16 $muted
# top quest progress strip
Round $g 40 219 1360 135 22 $paper $line;Txt $g 'A path made of small steps' 66 241 18 $ink $true;Txt $g 'Choose any world to continue or begin somewhere new.' 66 271 13 $muted
$g.DrawLine((New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(255,202,216,241),4)),156,315,1278,315)
$worlds2=@(@('Memory','4 tasks','world-memory.png'),@('Attention','2 tasks','world-attention.png'),@('Flexibility','3 tasks','world-flexibility.png'),@('Reasoning','2 tasks','world-reasoning.png'),@('Planning','Open','world-planning.png'))
for($i=0;$i -lt 5;$i++){ $cx=168+$i*274;$asset=Join-Path $art $worlds2[$i][2];ImageContain $g $asset ($cx-41) 277 82 62;$bub=Brush $blue;$g.FillEllipse($bub,$cx-9,306,18,18);$bub.Dispose();$bub=Brush ([System.Drawing.Color]::White);$g.FillEllipse($bub,$cx-3,312,6,6);$bub.Dispose();Txt $g $worlds2[$i][0] ($cx-43) 330 12 $ink $true}
# milestone cards
Txt $g 'WORLD MILESTONES' 44 387 11 $muted $true;Txt $g 'Activity remembered, one world at a time' 44 409 22 $ink $true
$milestones=@(@('Memory','Four saved tasks','Oct 16 · paired recall','4 evidence links','world-memory.png'),@('Attention','Two saved tasks','Oct 14 · target search','2 evidence links','world-attention.png'),@('Flexibility','Three saved tasks','Oct 13 · rule shift','3 evidence links','world-flexibility.png'),@('Reasoning','Two saved tasks','Oct 11 · pattern set','2 evidence links','world-reasoning.png'),@('Planning','Ready when you are','No saved task yet','Start with any challenge','world-planning.png'))
for($i=0;$i -lt 5;$i++){ $x=40+$i*276;Round $g $x 450 260 231 21 $paper $line;ImageContain $g (Join-Path $art $milestones[$i][4]) ($x+10) 452 240 112;Txt $g $milestones[$i][0] ($x+16) 566 18 $ink $true;Txt $g $milestones[$i][1] ($x+16) 594 13 $muted;Txt $g $milestones[$i][2] ($x+16) 618 12 $muted;Round $g ($x+16) 636 162 24 12 ([System.Drawing.Color]::FromArgb(255,241,246,241));Txt $g $milestones[$i][3] ($x+27) 641 11 $green $true;Txt $g 'Open world' ($x+16) 663 12 $blue $true }
# participation summary (XP explicitly separate)
Round $g 40 706 1360 116 22 ([System.Drawing.Color]::FromArgb(255,238,244,255)) ([System.Drawing.Color]::FromArgb(255,220,231,249));Pill $g 'PARTICIPATION ONLY' 66 725 162 ([System.Drawing.Color]::White) $blue;Txt $g '240 XP' 67 759 29 $blue $true;Txt $g 'Earned for showing up and playing.' 183 765 14 $ink $true;Txt $g 'XP is separate from task estimates and does not describe ability.' 183 788 12 $muted;Txt $g 'Next step: choose any open world' 1007 760 16 $ink $true;Txt $g 'No streaks or locked paths' 1007 787 12 $muted
Footer $g;Companion $g 1321 844; Save $b 'overview-quest.png'

