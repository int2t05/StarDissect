// Naive UI 主题映射:取值全部源自 UIUX tokens(UX-60),深浅两轴成对,组件零硬编码色值
import { darkTheme, lightTheme } from 'naive-ui'

export { darkTheme, lightTheme }

const fontFamily = '-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",system-ui,sans-serif'

const dark = {
  common: {
    primaryColor: '#e8a33d', primaryColorHover: '#f0b45a', primaryColorPressed: '#c98a2e', primaryColorSuppl: '#e8a33d',
    bodyColor: '#101014', cardColor: '#18181f', modalColor: '#20202a', popoverColor: '#20202a', tableColor: '#18181f', inputColor: '#20202a',
    borderColor: '#2b2b36', dividerColor: '#2b2b36',
    textColorBase: '#e9e9ee', textColor1: '#e9e9ee', textColor2: '#a3a3b3', textColor3: '#6e6e80',
    borderRadius: '6px', fontSizeMedium: '15px', fontFamily,
  },
}
const light = {
  common: {
    primaryColor: '#b06f0a', primaryColorHover: '#c9820d', primaryColorPressed: '#96600a', primaryColorSuppl: '#b06f0a',
    bodyColor: '#f7f7f8', cardColor: '#ffffff', modalColor: '#ffffff', popoverColor: '#ffffff', tableColor: '#ffffff', inputColor: '#ffffff',
    borderColor: '#e2e2e6', dividerColor: '#e2e2e6',
    textColorBase: '#1d1d22', textColor1: '#1d1d22', textColor2: '#5b5b66', textColor3: '#90909c',
    borderRadius: '6px', fontSizeMedium: '15px', fontFamily,
  },
}

export const themeOverrides = { dark, light }

export function naiveTheme(mode, os) {
  return (mode === 'auto' ? os : mode) === 'light' ? lightTheme : darkTheme
}

export function overridesFor(mode, os) {
  return (mode === 'auto' ? os : mode) === 'light' ? themeOverrides.light : themeOverrides.dark
}
