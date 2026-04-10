import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import LanguageDetector from 'i18next-browser-languagedetector'

import commonFr from './locales/fr/common.json'
import dashboardFr from './locales/fr/dashboard.json'
import vmFr from './locales/fr/vm.json'
import adminFr from './locales/fr/admin.json'
import authFr from './locales/fr/auth.json'
import charterFr from './locales/fr/charter.json'

import commonEn from './locales/en/common.json'
import dashboardEn from './locales/en/dashboard.json'
import vmEn from './locales/en/vm.json'
import adminEn from './locales/en/admin.json'
import authEn from './locales/en/auth.json'
import charterEn from './locales/en/charter.json'

import commonZh from './locales/zh/common.json'
import dashboardZh from './locales/zh/dashboard.json'
import vmZh from './locales/zh/vm.json'
import adminZh from './locales/zh/admin.json'
import authZh from './locales/zh/auth.json'
import charterZh from './locales/zh/charter.json'

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      fr: { common: commonFr, dashboard: dashboardFr, vm: vmFr, admin: adminFr, auth: authFr, charter: charterFr },
      en: { common: commonEn, dashboard: dashboardEn, vm: vmEn, admin: adminEn, auth: authEn, charter: charterEn },
      zh: { common: commonZh, dashboard: dashboardZh, vm: vmZh, admin: adminZh, auth: authZh, charter: charterZh },
    },
    fallbackLng: 'fr',
    defaultNS: 'common',
    interpolation: { escapeValue: false },
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
    },
  })

export default i18n
