# MCP Compose UI

React-based web interface for managing MCP Compose.

## Features

- 📊 **Dashboard**: System overview and quick stats
- 🖥️ **Server Management**: Start, stop, restart MCP servers
- 🔧 **Tool Browser**: Search and invoke MCP tools
- ⚙️ **Configuration**: Edit composer settings
- 🔄 **Translators**: Manage protocol translators
- 📝 **Logs**: Real-time log viewing
- 📈 **Metrics**: Performance monitoring
- 🌓 **Dark Mode**: Toggle between light and dark themes

## Tech Stack

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool
- **Tailwind CSS** - Styling
- **Zustand** - State management
- **React Query** - Data fetching
- **React Router** - Navigation
- **Axios** - HTTP client
- **Lucide React** - Icons

## Getting Started

### Prerequisites

- Node.js >= 18
- npm or yarn

### Installation

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

### Development

The dev server runs on `http://localhost:3000` and proxies API requests to `http://localhost:8000`.

To change the API URL, create a `.env` file:

```bash
VITE_API_URL=http://your-api-url:8000/api/v1
```

### Building

```bash
npm run build
```

Output is in the `dist/` directory.

## Project Structure

```
ui/
├── src/
│   ├── api/              # API client
│   │   └── client.ts     # Axios configuration and API methods
│   ├── components/       # Reusable components
│   │   └── Layout.tsx    # Main layout with sidebar
│   ├── pages/            # Page components
│   │   ├── Dashboard.tsx
│   │   ├── Servers.tsx
│   │   ├── Tools.tsx
│   │   ├── Configuration.tsx
│   │   ├── Translators.tsx
│   │   ├── Logs.tsx
│   │   ├── Metrics.tsx
│   │   └── Settings.tsx
│   ├── store/            # State management
│   │   └── theme.ts      # Theme store (Zustand)
│   ├── App.tsx           # Main app component
│   ├── main.tsx          # Entry point
│   └── index.css         # Global styles
├── public/               # Static assets
├── index.html            # HTML template
├── package.json          # Dependencies
├── tsconfig.json         # TypeScript config
├── vite.config.ts        # Vite config
└── tailwind.config.js    # Tailwind config
```

## API Integration

The UI connects to the REST API at `/api/v1`. All API methods are defined in `src/api/client.ts`:

- Health & Version
- Server Management
- Tools, Prompts, Resources
- Configuration
- Status & Metrics
- Translators

## Theme

The app supports light and dark themes using Tailwind CSS. The theme preference is persisted in localStorage.

Toggle theme using the sun/moon icon in the sidebar header.

## Development Roadmap

### Week 13 (Current) ✅
- [x] Project setup (Vite + React + TypeScript)
- [x] Routing configuration
- [x] Layout with sidebar navigation
- [x] Theme system (light/dark mode)
- [x] API client setup
- [x] Page placeholders

### Week 14 (Next)
- [ ] Server Management UI
- [ ] Tool Browser with search/filter
- [ ] Configuration Editor
- [ ] Status Dashboard

### Week 15
- [ ] Log Viewer with streaming
- [ ] Metrics Dashboard with charts
- [ ] Translator Management
- [ ] Advanced UI polish

### Week 16
- [ ] Documentation
- [ ] Packaging & deployment
- [ ] Docker integration
- [ ] Production optimizations

## Contributing

This is part of the MCP Compose project. See the main README for contribution guidelines.

## License

BSD 3-Clause License - see LICENSE file in the project root.
