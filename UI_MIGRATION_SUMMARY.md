# MCP Compose UI Migration Summary

## Overview

The MCP Compose UI has been migrated from a Tailwind CSS + Radix UI stack to **Primer React** (GitHub's design system) with **TanStack Query** for API state management. Additionally, username/password authentication has been added with configurable credentials.

## Changes Made

### 1. Backend Changes

#### Configuration ([mcp_compose/config.py](mcp_compose/config.py))
- Added `BasicAuthConfig` model for username/password authentication
- Added `BASIC` to `AuthProvider` enum
- Updated `AuthenticationConfig` to include `basic` field

#### Authentication ([mcp_compose/auth.py](mcp_compose/auth.py))
- Added `BASIC` to `AuthType` enum  
- Implemented `BasicAuthenticator` class with:
  - Username/password validation with constant-time comparison
  - Password hashing using SHA-256
  - Session token generation
  - 24-hour session expiration

#### API Routes ([mcp_compose/api/routes/auth.py](mcp_compose/api/routes/auth.py))
**New file** with endpoints:
- `POST /api/v1/auth/login` - Authenticate with username/password
- `POST /api/v1/auth/logout` - Invalidate session
- `GET /api/v1/auth/me` - Get current user information

#### API App ([mcp_compose/api/app.py](mcp_compose/api/app.py))
- Registered auth routes in `register_routes()`

#### Configuration Reference ([references/mcp_compose.toml](references/mcp_compose.toml))
Added example basic auth configuration:
```toml
[authentication.basic]
username = "${MCP_USERNAME}"  # or "admin"
password = "${MCP_PASSWORD}"  # or "secret"
```

### 2. Frontend Changes

#### Package Dependencies ([ui/package.json](ui/package.json))
**Removed:**
- All `@radix-ui/*` components
- `tailwindcss`, `autoprefixer`, `postcss`
- `class-variance-authority`, `clsx`, `tailwind-merge`
- `lucide-react` icons
- `zustand` state management

**Added:**
- `@primer/react` (^36.27.0) - GitHub's React component library
- `@primer/octicons-react` (^19.11.0) - GitHub's icon set
- `@tanstack/react-query-devtools` (^5.14.2) - Dev tools for TanStack Query
- `styled-components` (^6.1.13) - Required peer dependency for Primer React

**Kept:**
- `@tanstack/react-query` (already in use)
- `axios` (API client)
- `react-router-dom` (routing)
- `recharts` (charts)

#### Styling ([ui/src/index.css](ui/src/index.css))
- Removed all Tailwind CSS directives
- Added simple CSS reset optimized for Primer React
- Primer React provides its own comprehensive design system

#### Application Entry ([ui/src/main.tsx](ui/src/main.tsx))
- Wrapped app in Primer's `ThemeProvider` with `colorMode="auto"`
- Wrapped app in `BaseStyles` for global Primer styles
- Added `ReactQueryDevtools` for development

#### Authentication State ([ui/src/store/auth.tsx](ui/src/store/auth.tsx))
**New file** - React Context-based auth state:
- `AuthProvider` component
- `useAuth()` hook
- Manages token, userId, and authentication state
- Persists to localStorage

#### API Client ([ui/src/api/client.ts](ui/src/api/client.ts))
Added auth endpoints:
```typescript
login: (username: string, password: string)
logout: ()
getCurrentUser: ()
```

#### Login Page ([ui/src/pages/Login.tsx](ui/src/pages/Login.tsx))
**New file** - Primer React login form with:
- Username and password inputs
- Error handling with Flash component
- Loading states
- TanStack Query mutation for login
- Redirect on success

#### Layout Component ([ui/src/components/Layout.tsx](ui/src/components/Layout.tsx))
Migrated from Tailwind to Primer React:
- Uses Primer's `Box`, `NavList`, `Button` components
- Uses Octicons instead of Lucide icons
- Integrated theme toggle using `useTheme()` from Primer
- Added logout button

#### App Router ([ui/src/App.tsx](ui/src/App.tsx))
- Wrapped in `AuthProvider`
- Added `ProtectedRoute` component
- Login route redirects to dashboard when authenticated
- All other routes require authentication

## Configuration Example

### Enable Basic Authentication

In your `mcp_compose.toml`:

```toml
[authentication]
enabled = true
providers = ["basic"]
default_provider = "basic"

[authentication.basic]
username = "admin"
password = "your-secure-password"
```

Or use environment variables:

```toml
[authentication.basic]
username = "${MCP_USERNAME}"
password = "${MCP_PASSWORD}"
```

Then set:
```bash
export MCP_USERNAME=admin
export MCP_PASSWORD=your-secure-password
```

## Running the Application

### Install Dependencies

```bash
cd ui
npm install
```

### Development Mode

```bash
npm run dev
```

### Build for Production

```bash
npm run build
```

## Next Steps

### Remaining Page Migrations

The following pages still need to be migrated from Tailwind to Primer React components:

- [ ] [Dashboard.tsx](ui/src/pages/Dashboard.tsx)
- [ ] [Servers.tsx](ui/src/pages/Servers.tsx)
- [ ] [Tools.tsx](ui/src/pages/Tools.tsx)
- [ ] [Configuration.tsx](ui/src/pages/Configuration.tsx)
- [ ] [Translators.tsx](ui/src/pages/Translators.tsx)
- [ ] [Logs.tsx](ui/src/pages/Logs.tsx)
- [ ] [Metrics.tsx](ui/src/pages/Metrics.tsx)
- [ ] [Settings.tsx](ui/src/pages/Settings.tsx)

### Migration Guide for Pages

Replace Tailwind classes with Primer components:

**Before (Tailwind):**
```tsx
<div className="bg-card border border-border rounded-lg p-6">
  <h2 className="text-lg font-semibold">Title</h2>
  <p className="text-muted-foreground">Description</p>
</div>
```

**After (Primer):**
```tsx
<Box sx={{
  bg: 'canvas.subtle',
  borderWidth: 1,
  borderStyle: 'solid',
  borderColor: 'border.default',
  borderRadius: 2,
  p: 3,
}}>
  <Heading sx={{ fontSize: 2, mb: 2 }}>Title</Heading>
  <Text sx={{ color: 'fg.muted' }}>Description</Text>
</Box>
```

### Common Component Replacements

| Tailwind/Radix | Primer React |
|----------------|--------------|
| `<div>` with classes | `<Box>` with sx prop |
| `<button>` | `<Button>` |
| `<input>` | `<TextInput>` |
| `<h1>`, `<h2>` | `<Heading>` |
| `<p>` | `<Text>` |
| Lucide icons | Octicons |
| Custom alerts | `<Flash>` |
| Custom dialogs | `<Dialog>` |
| Custom selects | `<Select>` |
| Custom tabs | `<TabNav>` / `<UnderlineNav>` |

### Resources

- [Primer React Documentation](https://primer.style/react/)
- [Primer Design System](https://primer.style/)
- [Octicons](https://primer.style/foundations/icons)
- [TanStack Query Docs](https://tanstack.com/query/latest)

## Security Notes

- Passwords are hashed using SHA-256 before storage/comparison
- Sessions expire after 24 hours
- Constant-time comparison prevents timing attacks
- Tokens are stored in localStorage (consider httpOnly cookies for production)

## Breaking Changes

1. **Theme Store Removed**: The zustand-based theme store has been replaced with Primer's built-in theme system
2. **Icon Library**: Lucide icons replaced with Octicons
3. **CSS Framework**: Tailwind CSS completely removed in favor of Primer's design system
4. **Authentication Required**: UI now requires login by default when authentication is enabled

## Files Removed

You can safely delete:
- `ui/tailwind.config.js`
- `ui/postcss.config.js`  
- `ui/src/store/theme.ts`

## Environment Variables

Add to `ui/.env`:
```
VITE_API_URL=http://localhost:8080/api/v1
```
