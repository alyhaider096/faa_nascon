# Reproducible, code-drawn typographic placeholders until the tenant supplies a logo.
# Run from any directory on Windows: powershell -File mobile/scripts/generate-brand-assets.ps1
Add-Type -AssemblyName System.Drawing
$assetDir = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\assets'))

function New-BrandPng([string]$target, [int]$size, [int]$fontSize) {
  $bitmap = [System.Drawing.Bitmap]::new($size, $size)
  $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
  $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
  $graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
  $background = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml('#071522'))
  $foreground = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml('#F4F8FC'))
  $accent = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml('#8EE6C2'))
  $font = [System.Drawing.Font]::new('Segoe UI', $fontSize, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
  try {
    $graphics.FillRectangle($background, 0, 0, $size, $size)
    $format = [System.Drawing.StringFormat]::new()
    $format.Alignment = [System.Drawing.StringAlignment]::Center
    $format.LineAlignment = [System.Drawing.StringAlignment]::Center
    $graphics.DrawString('LO', $font, $foreground, [System.Drawing.RectangleF]::new(0, 0, $size, $size), $format)
    $barWidth = [int]($size * 0.29)
    $barHeight = [int]($size * 0.018)
    $graphics.FillRectangle($accent, [int](($size - $barWidth) / 2), [int]($size * 0.74), $barWidth, $barHeight)
    $bitmap.Save($target, [System.Drawing.Imaging.ImageFormat]::Png)
    $format.Dispose()
  } finally {
    $font.Dispose(); $accent.Dispose(); $foreground.Dispose(); $background.Dispose(); $graphics.Dispose(); $bitmap.Dispose()
  }
}

New-BrandPng (Join-Path $assetDir 'leagueops-icon.png') 1024 350
New-BrandPng (Join-Path $assetDir 'leagueops-splash.png') 512 176
