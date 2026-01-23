# Medical Knowledge Management Frontend

Modern frontend UI for the medical knowledge management system built with Astro.js and React.

## Features

- ✅ **Patient Chat Interface** - Real-time WebSocket chat with medical assistant
- ✅ **Patient Context Sidebar** - Display patient diagnoses, medications, allergies
- ✅ **Safety Warnings** - Prominent display of contraindication alerts
- ✅ **Knowledge Graph Visualization** - Interactive D3.js graph (coming soon)
- ✅ **Admin Dashboard** - System monitoring and patient management (coming soon)

## Tech Stack

- **Astro.js** - Static site generation with island architecture
- **React** - Interactive components
- **TypeScript** - Type safety
- **Tailwind CSS** - Utility-first styling
- **Zustand** - State management
- **WebSockets** - Real-time communication

## Getting Started

### Prerequisites

- Node.js 20+
- Backend services running (Neo4j, Redis, FastAPI)

### Development

```bash
# Install dependencies
npm install

# Start dev server (with backend proxy)
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

### Development Server

The dev server runs on `http://localhost:3000` and proxies API requests to `http://localhost:8000`.

## Project Structure

```
frontend/
├── src/
│   ├── components/       # React components
│   │   ├── chat/        # Chat interface
│   │   ├── graph/       # Graph visualization
│   │   ├── admin/       # Admin dashboard
│   │   ├── dda/         # DDA management
│   │   └── ui/          # Reusable UI components
│   ├── layouts/         # Astro layouts
│   ├── pages/           # File-based routing
│   ├── lib/             # Utilities (API client)
│   ├── hooks/           # React hooks
│   ├── stores/          # Zustand stores
│   ├── types/           # TypeScript types
│   └── styles/          # Global styles
├── public/              # Static assets
└── astro.config.mjs    # Astro configuration
```

## Usage

### Patient Chat

Navigate to `/chat/{patientId}` to start a chat session.

Example: `http://localhost:3000/chat/patient:demo`

### Home Page

The home page displays cards for all 4 main features:
- Patient Chat
- Knowledge Graph
- Admin Dashboard
- DDA Management

## Environment Variables

Create a `.env` file:

```bash
PUBLIC_API_URL=http://localhost:8000
```

## Production Deployment

The frontend is served by FastAPI in production:

1. Build the frontend:
   ```bash
   npm run build
   ```

2. FastAPI serves the static files from `frontend/dist/`

3. Access via `http://localhost:8000/`

## WebSocket Connection

The chat interface connects to WebSocket endpoints:
- Endpoint: `ws://localhost:8000/ws/chat/{patient_id}/{session_id}`
- Auto-reconnects on disconnect
- Real-time message streaming

## Next Steps

- [ ] Add Knowledge Graph visualization (D3.js)
- [ ] Build Admin Dashboard
- [ ] Implement DDA Management UI
- [ ] Add authentication
- [ ] Add E2E tests with Playwright
