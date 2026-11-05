// Naive UI 映射与 tokens.css 对齐，管理面和报告站共用底色、文字与琥珀色阶
import { darkTheme, lightTheme } from 'naive-ui'

export { darkTheme, lightTheme }

const fontFamily = '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif'

const dark = {
  common: {
    primaryColor: '#e8a33d', primaryColorHover: '#f0b45a', primaryColorPressed: '#c98a2e', primaryColorSuppl: '#e8a33d',
    bodyColor: '#1b1b1f', cardColor: '#202127', modalColor: '#202127', popoverColor: '#292a30', tableColor: '#202127', inputColor: '#292a30',
    borderColor: 'rgba(255, 255, 255, 0.12)', dividerColor: 'rgba(255, 255, 255, 0.1)',
    textColorBase: '#e6e8eb', textColor1: '#e6e8eb', textColor2: '#b2b6bd', textColor3: '#8b9098',
    borderRadius: '7px', fontSizeMedium: '15px', fontFamily,
  },
}
const light = {
  common: {
    primaryColor: '#965e00', primaryColorHover: '#834f00', primaryColorPressed: '#704300', primaryColorSuppl: '#965e00',
    bodyColor: '#f6f8fa', cardColor: '#ffffff', modalColor: '#ffffff', popoverColor: '#ffffff', tableColor: '#ffffff', inputColor: '#ffffff',
    borderColor: 'rgba(31, 35, 40, 0.12)', dividerColor: 'rgba(31, 35, 40, 0.1)',
    textColorBase: '#1f2328', textColor1: '#1f2328', textColor2: '#57606a', textColor3: '#6e7781',
    borderRadius: '7px', fontSizeMedium: '15px', fontFamily,
  },
}

export const themeOverrides = { dark, light }

export function naiveTheme(mode, os) {
  return (mode === 'auto' ? os : mode) === 'light' ? lightTheme : darkTheme
}

export function overridesFor(mode, os) {
  return (mode === 'auto' ? os : mode) === 'light' ? themeOverrides.light : themeOverrides.dark
}
