/**
 * Copyright (C) 2025 Xiaomi Corporation
 * This software may be used and distributed according to the terms of the Xiaomi Miloco License Agreement.
 */

// Ant Design theme config
import { theme } from 'antd';

// dark theme config
export const darkTheme = {
  algorithm: theme.darkAlgorithm,
  token: {
    // primary color — Claude orange
    colorPrimary: '#cba6f7',        // Mauve
    colorPrimaryHover: '#d6baff',
    colorPrimaryActive: '#b894e8',

    // functional colors
    colorSuccess: '#a6e3a1',        // Green
    colorWarning: '#f9e2af',        // Yellow
    colorError: '#f38ba8',          // Red
    colorInfo: '#89b4fa',           // Blue

    // background
    colorBgContainer: '#313244',    // Surface0
    colorBgElevated: '#45475a',     // Surface1
    colorBgLayout: '#1e1e2e',       // Base
    colorBgSpotlight: 'rgba(205, 214, 244, 0.9)',
    colorBgMask: 'rgba(17, 17, 27, 0.7)',

    // text
    colorText: '#cdd6f4',           // Text
    colorTextSecondary: '#bac2de',  // Subtext1
    colorTextTertiary: '#a6adc8',   // Subtext0
    colorTextQuaternary: '#9399b2', // Overlay2
    colorTextDisabled: '#7f849c',   // Overlay1

    // border
    colorBorder: '#585b70',         // Surface2
    colorBorderSecondary: '#45475a', // Surface1

    // border radius
    borderRadius: 8,
    borderRadiusLG: 12,
    borderRadiusSM: 6,
    borderRadiusXS: 4,

    // shadows
    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.3)',
    boxShadowSecondary: '0 1px 4px rgba(0, 0, 0, 0.2)',
    boxShadowTertiary: '0 4px 16px rgba(0, 0, 0, 0.4)',

    // font family
    fontFamily: "'MiSans', system-ui, Avenir, Helvetica, Arial, sans-serif",
    fontSize: 14,
    fontSizeLG: 16,
    fontSizeSM: 12,
    fontSizeXL: 20,
    fontSizeHeading1: 38,
    fontSizeHeading2: 30,
    fontSizeHeading3: 24,
    fontSizeHeading4: 20,
    fontSizeHeading5: 16,

    // line height
    lineHeight: 1.5,
    lineHeightLG: 1.8,
    lineHeightSM: 1.2,

    // spacing
    padding: 16,
    paddingLG: 24,
    paddingMD: 16,
    paddingSM: 12,
    paddingXS: 8,
    paddingXXS: 4,

    margin: 16,
    marginLG: 24,
    marginMD: 16,
    marginSM: 12,
    marginXS: 8,
    marginXXS: 4,

    // component specific config
    controlHeight: 32,
    controlHeightLG: 40,
    controlHeightSM: 24,
    controlHeightXS: 20,

    // animations
    motionDurationFast: '0.1s',
    motionDurationMid: '0.2s',
    motionDurationSlow: '0.3s',
    motionEaseInOut: 'cubic-bezier(0.645, 0.045, 0.355, 1)',
    motionEaseOut: 'cubic-bezier(0.215, 0.61, 0.355, 1)',
    motionEaseIn: 'cubic-bezier(0.55, 0.055, 0.675, 0.19)',
  },
  components: {
    Menu: {
      borderRadius: 8,
      itemBorderRadius: 6,
      itemSelectedBg: 'rgba(203, 166, 247, 0.2)',
      itemActiveBg: 'rgba(203, 166, 247, 0.15)',
      itemHoverBg: 'rgba(88, 91, 112, 0.4)',
      itemHoverColor: '#cdd6f4',
      itemSelectedColor: '#cba6f7',
      algorithm: true,
      borderWidth: 0,
      inlineIndent: 0,
    },
    Drawer: {
      algorithm: true,
    },
    Button: {
      borderRadius: 8,
      controlHeight: 32,
      controlHeightLG: 40,
      controlHeightSM: 24,
      paddingInline: 16,
      paddingInlineLG: 24,
      paddingInlineSM: 12,
      algorithm: true,
      defaultShadow: 'none',
    },
    Input: {
      borderRadius: 8,
      controlHeight: 32,
      controlHeightLG: 40,
      controlHeightSM: 24,
      paddingInline: 12,
      paddingInlineLG: 16,
      paddingInlineSM: 8,
      algorithm: true,
      borderWidth: 1,
      activeShadow: '0 0 0 2px rgba(203, 166, 247, 0.3)',
    },
    Select: {
      borderRadius: 8,
      controlHeight: 32,
      controlHeightLG: 40,
      controlHeightSM: 24,
      algorithm: true,
      optionSelectedBg: 'rgba(203, 166, 247, 0.2)',
    },
    Card: {
      borderRadius: 12,
      algorithm: true,
    },
    Modal: {
      borderRadius: 12,
      algorithm: true,
    },
    Table: {
      borderRadius: 8,
      algorithm: true,
    },
    Tag: {
      borderRadius: 6,
      algorithm: true,
    },
    Badge: {
      algorithm: true,
    },
    Progress: {
      algorithm: true,
    },
    Slider: {
      algorithm: true,
    },
    Switch: {
      algorithm: true,
    },
    Checkbox: {
      borderRadius: 4,
      algorithm: true,
    },
    Radio: {
      algorithm: true,
    },
  },
};

// global theme config
export const globalTheme = {
  algorithm: theme.defaultAlgorithm,
  token: {
    // primary color — Claude orange
    colorPrimary: '#8839ef',        // Latte Mauve
    colorPrimaryHover: '#9040ff',
    colorPrimaryActive: '#7a31d6',
    colorPrimaryBg: 'rgba(136, 57, 239, 0.08)',
    colorPrimaryBgHover: 'rgba(136, 57, 239, 0.12)',
    colorPrimaryBorder: '#8839ef',
    colorPrimaryBorderHover: '#7a31d6',

    // functional colors
    colorSuccess: '#40a02b',        // Latte Green
    colorWarning: '#df8e1d',        // Latte Yellow
    colorError: '#d20f39',          // Latte Red
    colorInfo: '#1e66f5',           // Latte Blue

    // neutral colors
    colorText: '#4c4f69',           // Latte Text
    colorTextSecondary: '#5c5f77',  // Latte Subtext1
    colorTextTertiary: '#6c6f85',   // Latte Subtext0
    colorTextQuaternary: '#7c7f93', // Latte Overlay2
    colorTextDisabled: '#8c8fa1',   // Latte Overlay1

    // background colors
    colorBgContainer: '#ffffff',
    colorBgElevated: '#ffffff',
    colorBgLayout: '#eff1f5',       // Latte Base
    colorBgSpotlight: 'rgba(76, 79, 105, 0.85)',
    colorBgMask: 'rgba(0, 0, 0, 0.4)',

    // border colors
    colorBorder: '#ccd0da',         // Latte Surface0
    colorBorderSecondary: '#e6e9ef', // Latte Mantle

    // border radius
    borderRadius: 8,
    borderRadiusLG: 12,
    borderRadiusSM: 6,
    borderRadiusXS: 4,

    // shadows
    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
    boxShadowSecondary: '0 1px 4px rgba(0, 0, 0, 0.06)',
    boxShadowTertiary: '0 4px 16px rgba(0, 0, 0, 0.12)',

    // font family
    fontFamily: "'MiSans', system-ui, Avenir, Helvetica, Arial, sans-serif",
    fontSize: 14,
    fontSizeLG: 16,
    fontSizeSM: 12,
    fontSizeXL: 20,
    fontSizeHeading1: 38,
    fontSizeHeading2: 30,
    fontSizeHeading3: 24,
    fontSizeHeading4: 20,
    fontSizeHeading5: 16,

    // line height
    lineHeight: 1.5,
    lineHeightLG: 1.8,
    lineHeightSM: 1.2,

    // spacing
    padding: 16,
    paddingLG: 24,
    paddingMD: 16,
    paddingSM: 12,
    paddingXS: 8,
    paddingXXS: 4,

    margin: 16,
    marginLG: 24,
    marginMD: 16,
    marginSM: 12,
    marginXS: 8,
    marginXXS: 4,

    // component specific config
    controlHeight: 32,
    controlHeightLG: 40,
    controlHeightSM: 24,
    controlHeightXS: 20,

    // animations
    motionDurationFast: '0.1s',
    motionDurationMid: '0.2s',
    motionDurationSlow: '0.3s',
    motionEaseInOut: 'cubic-bezier(0.645, 0.045, 0.355, 1)',
    motionEaseOut: 'cubic-bezier(0.215, 0.61, 0.355, 1)',
    motionEaseIn: 'cubic-bezier(0.55, 0.055, 0.675, 0.19)',
  },
  components: {
    Button: {
      borderRadius: 8,
      controlHeight: 32,
      controlHeightLG: 40,
      controlHeightSM: 24,
      paddingInline: 16,
      paddingInlineLG: 24,
      paddingInlineSM: 12,
      algorithm: true,
      defaultShadow: 'none',
    },
    Input: {
      borderRadius: 8,
      controlHeight: 32,
      controlHeightLG: 40,
      controlHeightSM: 24,
      paddingInline: 12,
      paddingInlineLG: 16,
      paddingInlineSM: 8,
      algorithm: true,
      borderWidth: 1,
      activeShadow: '0 0 0 2px rgba(136, 57, 239, 0.2)',
    },
    Select: {
      borderRadius: 8,
      controlHeight: 32,
      controlHeightLG: 40,
      controlHeightSM: 24,
      algorithm: true,
      optionSelectedBg: 'rgba(136, 57, 239, 0.08)',
    },
    Menu: {
      borderRadius: 8,
      itemBorderRadius: 6,
      itemSelectedBg: 'rgba(136, 57, 239, 0.1)',
      itemActiveBg: 'rgba(136, 57, 239, 0.1)',
      itemHoverBg: 'rgba(76, 79, 105, 0.06)',
      itemHoverColor: '#4c4f69',
      itemSelectedColor: '#8839ef',
      algorithm: true,
      borderWidth: 0,
      inlineIndent: 0,
      itemPaddingInline: 0,
      collapsedIconSize: 32,
      collapsedWidth: 100,
      itemHeight: 48,
      horizontalLineHeight: '70px',
    },
    Card: {
      borderRadius: 12,
      algorithm: true,
    },
    Modal: {
      borderRadius: 12,
      algorithm: true,
    },
    Drawer: {
      algorithm: true,
    },
    Table: {
      borderRadius: 8,
      algorithm: true,
    },
    Tag: {
      borderRadius: 6,
      algorithm: true,
    },
    Badge: {
      algorithm: true,
    },
    Progress: {
      algorithm: true,
    },
    Slider: {
      algorithm: true,
    },
    Switch: {
      algorithm: true,
    },
    Checkbox: {
      borderRadius: 4,
      algorithm: true,
    },
    Radio: {
      algorithm: true,
    },
  },
};

// export theme tokens for other components
export const themeTokens = {
  // primary color — Claude orange
  primary: '#cba6f7',
  primaryHover: '#d6baff',
  primaryActive: '#b894e8',
  primaryLight: 'rgba(203, 166, 247, 0.15)',
  primaryLighter: 'rgba(203, 166, 247, 0.08)',

  // primary color variants
  primary90: 'rgba(203, 166, 247, 0.9)',
  primary80: 'rgba(203, 166, 247, 0.8)',
  primary70: 'rgba(203, 166, 247, 0.7)',
  primary60: 'rgba(203, 166, 247, 0.6)',
  primary50: 'rgba(203, 166, 247, 0.5)',
  primary40: 'rgba(203, 166, 247, 0.4)',
  primary30: 'rgba(203, 166, 247, 0.3)',
  primary20: 'rgba(203, 166, 247, 0.2)',
  primary10: 'rgba(203, 166, 247, 0.1)',
  primary05: 'rgba(203, 166, 247, 0.05)',

  // functional colors
  success: '#a6e3a1',
  warning: '#f9e2af',
  error: '#f38ba8',
  info: '#89b4fa',

  // spacing
  spacing: {
    xs: 4,
    sm: 8,
    md: 16,
    lg: 24,
    xl: 32,
    xxl: 48,
  },

  // border radius
  borderRadius: {
    sm: 6,
    md: 8,
    lg: 12,
    xl: 16,
  },

  // shadows
  boxShadow: {
    light: '0 1px 4px rgba(0, 0, 0, 0.06)',
    default: '0 2px 8px rgba(0, 0, 0, 0.08)',
    dark: '0 4px 16px rgba(0, 0, 0, 0.12)',
    primary: '0 2px 8px rgba(203, 166, 247, 0.3)',
  },

  // animations
  transition: {
    duration: '0.2s',
    timing: 'cubic-bezier(0.645, 0.045, 0.355, 1)',
  },


};
