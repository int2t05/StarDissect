// Naive UI 映射与 tokens.css 对齐，两个界面共用中性底色与克制的琥珀强调色
import { darkTheme, lightTheme } from 'naive-ui'

export { darkTheme, lightTheme }

const fontFamily = '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif'

const dark = {
  common: {
    primaryColor: '#d5a052', primaryColorHover: '#e0ad62', primaryColorPressed: '#c28d40', primaryColorSuppl: '#d5a052',
    bodyColor: '#1b1b1f', cardColor: '#202127', modalColor: '#202127', popoverColor: '#292a30', tableColor: '#202127', inputColor: '#292a30',
    borderColor: 'rgba(255, 255, 255, 0.12)', dividerColor: 'rgba(255, 255, 255, 0.1)',
    textColorBase: '#e6e8eb', textColor1: '#e6e8eb', textColor2: '#b2b6bd', textColor3: '#8b9098',
    borderRadius: '6px', fontSizeMedium: '15px', fontFamily,
  },
}
const light = {
  common: {
    primaryColor: '#875b1b', primaryColorHover: '#754c15', primaryColorPressed: '#63400f', primaryColorSuppl: '#875b1b',
    bodyColor: '#f6f8fa', cardColor: '#ffffff', modalColor: '#ffffff', popoverColor: '#ffffff', tableColor: '#ffffff', inputColor: '#ffffff',
    borderColor: 'rgba(31, 35, 40, 0.12)', dividerColor: 'rgba(31, 35, 40, 0.1)',
    textColorBase: '#20242a', textColor1: '#20242a', textColor2: '#515963', textColor3: '#68717c',
    borderRadius: '6px', fontSizeMedium: '15px', fontFamily,
  },
}

export const themeOverrides = { dark, light }

export function naiveTheme(mode) {
  return mode === 'dark' ? darkTheme : lightTheme
}

export function overridesFor(mode) {
  return mode === 'dark' ? themeOverrides.dark : themeOverrides.light
}
