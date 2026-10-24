// The login gate for clicks that need an account (the dialog itself is LoginProvider in LoginDialog.tsx).
//
//   useRequireLogin()  -> requireLogin(action?): runs `action` now when logged in, else after a login in the
//                         dialog (closing the dialog drops it)
import { createContext, useContext } from 'react'

export type RequireLogin = (action?: () => void) => void

export const RequireLoginContext = createContext<RequireLogin>(action => action?.())

export const useRequireLogin = () => useContext(RequireLoginContext)
