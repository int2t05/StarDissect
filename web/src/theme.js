// Naive UI 主题映射:取值全部源自 UIUX tokens(UX-60/63),深浅两轴成对,组件零硬编码色值
// 风格基线(UX-63,Apple 式):单一强调色、pill 主动作、hairline 细线、无装饰阴影、display 负字距
import { darkTheme, lightTheme } from 'naive-ui'

export { darkTheme, lightTheme }

const fontFamily = '-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",system-ui,sans-serif'

const dark = {
  common: {
    primaryColor: '#e8a33d', primaryColorHover: '#f0b45a', primaryColorPressed: '#c98a2e', primaryColorSuppl: '#e8a33d',
    bodyColor: '#000000', cardColor: '#1d1d1f', modalColor: '#1d1d1f', popoverColor: '#2a2a2c', tableColor: '#1d1d1f', inputColor: '#2a2a2c',
    borderColor: 'rgba(255, 255, 255, 0.1)', dividerColor: 'rgba(255, 255, 255, 0.08)',
    textColorBase: '#f5f5f7', textColor1: '#f5f5f7', textColor2: '#a1a1a6', textColor3: '#6e6e73',
    borderRadius: '8px', fontSizeMedium: '15px', fontFamily,
  },
}
const light = {
  common: {
    primaryColor: '#b06f0a', primaryColorHover: '#c9820d', primaryColorPressed: '#96600a', primaryColorSuppl: '#b06f0a',
    bodyColor: '#f5f5f7', cardColor: '#ffffff', modalColor: '#ffffff', popoverColor: '#ffffff', tableColor: '#ffffff', inputColor: '#ffffff',
    borderColor: 'rgba(0, 0, 0, 0.08)', dividerColor: 'rgba(0, 0, 0, 0.06)',
    textColorBase: '#1d1d1f', textColor1: '#1d1d1f', textColor2: '#515154', textColor3: '#86868b',
    borderRadius: '8px', fontSizeMedium: '15px', fontFamily,
  },
}

export const themeOverrides = { dark, light }

export function naiveTheme(mode, os) {
  return (mode === 'auto' ? os : mode) === 'light' ? lightTheme : darkTheme
}

export function overridesFor(mode, os) {
  return (mode === 'auto' ? os : mode) === 'light' ? themeOverrides.light : themeOverrides.dark
}
