# MCP Compose UI - Quick Start Guide

## Setup and Run

### 1. Install Dependencies

```bash
cd ui
npm install
```

### 2. Configure Authentication (Backend)

Create or update `mcp_compose.toml` in your project root:

```toml
[authentication]
enabled = true
providers = ["basic"]
default_provider = "basic"

[authentication.basic]
username = "admin"
password = "changeme"
```

### 3. Start the Backend

```bash
# From the project root
python -m mcp_compose --config mcp_compose.toml
```

The API will start on `http://localhost:8080`

### 4. Start the UI Development Server

```bash
# From the ui directory
npm run dev
```

The UI will start on `http://localhost:5173` (or next available port)

### 5. Login

Navigate to `http://localhost:5173` and login with:
- **Username:** `admin`
- **Password:** `changeme` (or whatever you configured)

## Development Workflow

### Hot Reload

Both frontend and backend support hot reloading:
- **Frontend:** Vite dev server automatically reloads on file changes
- **Backend:** Restart the server after config or code changes

### API Proxy

In development, Vite proxies API requests to the backend. Configure in `vite.config.ts`:

```typescript
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
})
```

## Building for Production

### 1. Build the UI

```bash
cd ui
npm run build
```

This creates optimized static files in `ui/dist/`

### 2. Configure Backend to Serve UI

Update `mcp_compose.toml`:

```toml
[ui]
enabled = true
framework = "react"
mode = "embedded"
path = "/ui"
```

### 3. Copy Build to Backend

```bash
# From project root
cp -r ui/dist/* path/to/static/ui/
```

### 4. Start Backend

```bash
python -m mcp_compose --config mcp_compose.toml
```

Now access the UI at `http://localhost:8080/ui`

## Environment Variables

### Backend

```bash
export MCP_USERNAME=admin
export MCP_PASSWORD=your-secure-password
```

### Frontend (Development)

Create `ui/.env`:

```env
VITE_API_URL=http://localhost:8080/api/v1
```

## Migrating Existing Pages to Primer React

See [Dashboard.example.tsx](src/pages/Dashboard.example.tsx) for a complete example.

### Key Changes

1. **Replace Tailwind classes with Primer Box + sx prop:**

```tsx
// Before
<div className="bg-card border border-border rounded-lg p-6">

// After
<Box sx={{
  bg: 'canvas.subtle',
  borderWidth: 1,
  borderStyle: 'solid',
  borderColor: 'border.default',
  borderRadius: 2,
  p: 3,
}}>
```

2. **Use Primer components:**

```tsx
import { Box, Button, Heading, Text } from '@primer/react'
```

3. **Use Octicons instead of Lucide:**

```tsx
// Before
import { Server, Wrench } from 'lucide-react'

// After
import { ServerIcon, ToolsIcon } from '@primer/octicons-react'
```

4. **Responsive grids:**

```tsx
<Box sx={{
  display: 'grid',
  gridTemplateColumns: ['1fr', '1fr 1fr', '1fr 1fr 1fr 1fr'],
  // mobile    tablet     desktop
  gap: 3,
}}>
```

## Primer React Styling Guide

### Color Tokens

- `canvas.default` - Main background
- `canvas.subtle` - Card backgrounds
- `fg.default` - Primary text
- `fg.muted` - Secondary text
- `accent.subtle` - Accent backgrounds
- `success.subtle` / `danger.subtle` - Status colors

### Spacing Scale

- `0` = 0px
- `1` = 4px
- `2` = 8px
- `3` = 16px
- `4` = 24px
- `5` = 32px
- `6` = 40px

### Font Sizes

- `0` = 12px (small)
- `1` = 14px (default)
- `2` = 16px
- `3` = 20px
- `4` = 24px
- `5` = 32px

## Troubleshooting

### "Not authenticated" errors

1. Check authentication is enabled in `mcp_compose.toml`
2. Verify credentials are correct
3. Check browser localStorage for `auth_token`
4. Clear localStorage and try logging in again

### CORS errors

Update backend CORS settings in `mcp_compose.toml`:

```toml
[api]
cors_enabled = true
cors_origins = ["http://localhost:5173", "http://localhost:3000"]
```

### Theme not applying

Make sure `ThemeProvider` and `BaseStyles` wrap your app in `main.tsx`:

```tsx
<ThemeProvider colorMode="auto">
  <BaseStyles>
    <App />
  </BaseStyles>
</ThemeProvider>
```

### API calls failing

1. Check backend is running on port 8080
2. Verify `VITE_API_URL` in `.env`
3. Check browser network tab for errors
4. Verify auth token is being sent in requests

## Testing

### Run Tests

```bash
npm run test
```

### Type Checking

```bash
npm run type-check
```

### Linting

```bash
npm run lint
```

## Resources

- [Primer React Docs](https://primer.style/react/)
- [TanStack Query Docs](https://tanstack.com/query/latest)
- [React Router Docs](https://reactrouter.com/)
- [Vite Docs](https://vitejs.dev/)

## Support

For issues or questions:
1. Check the [UI Migration Summary](../UI_MIGRATION_SUMMARY.md)
2. Review the example components
3. Consult Primer React documentation
4. Open an issue on GitHub
