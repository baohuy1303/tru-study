import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { ClerkProvider } from '@clerk/clerk-react'

// Import your Publishable Key
const PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY

if (!PUBLISHABLE_KEY) {
  console.warn("⚠️ Missing VITE_CLERK_PUBLISHABLE_KEY in frontend/.env!")
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {PUBLISHABLE_KEY ? (
      <ClerkProvider publishableKey={PUBLISHABLE_KEY} afterSignOutUrl="/">
        <App />
      </ClerkProvider>
    ) : (
      <div className="p-8 text-rose-500">
        <h1>Missing Clerk Publishable Key</h1>
        <p>Please add <b>VITE_CLERK_PUBLISHABLE_KEY</b> to your <code>frontend/.env</code> file.</p>
      </div>
    )}
  </StrictMode>,
)
