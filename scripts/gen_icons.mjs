// 图标栅格化:SVG → PNG 全尺寸 + ICO(UMD/ESM 双兼容用 createRequire)
// favicon 小尺寸用 bold 变体(切片简化),大尺寸用全细节定稿版
import { createRequire } from 'node:module'
import { execSync } from 'node:child_process'
import { copyFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const requireFromWeb = createRequire(new URL('../web/package.json', import.meta.url))  // sharp 安装于 web/
const sharp = requireFromWeb('sharp')

const pub = fileURLToPath(new URL('../web/public/', import.meta.url))

async function render(src, out, size) {
  await sharp(pub + src, { density: 512 })
    .resize(size, size)
    .png()
    .toFile(pub + out)
  console.log('✓', out, `${size}x${size}`)
}

// 大尺寸:全细节定稿版(favicon.svg)
await render('favicon.svg', 'apple-touch-icon.png', 180)
await render('favicon.svg', 'icon-192.png', 192)
await render('favicon.svg', 'icon-512.png', 512)
// 小尺寸:bold 变体(16/32/48)
await render('favicon-bold.svg', 'favicon-16.png', 16)
await render('favicon-bold.svg', 'favicon-32.png', 32)
await render('favicon-bold.svg', 'favicon-48.png', 48)

// ICO:三尺寸打包(Pillow,本机已装)
execSync('python -c "from PIL import Image; Image.open(\'favicon-16.png\').save(\'favicon.ico\', sizes=[(16,16),(32,32),(48,48)])"', { cwd: pub })
console.log('✓ favicon.ico')

