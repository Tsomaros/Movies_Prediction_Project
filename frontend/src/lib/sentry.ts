// The part of Sentry the app uses, loaded on its own by monitoring.ts: named imports let the bundler drop
// the rest of the package (replay, feedback, tracing), which a whole-package import('@sentry/browser') keeps.
export { captureException, init } from '@sentry/browser'
