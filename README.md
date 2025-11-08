# Agno Chatbot - React Frontend + FastAPI Backend

A full-stack chatbot application using Agno AI with a React frontend and FastAPI backend.

## Project Structure

```
aiboomi_project/
├── backend/
│   └── api.py          # FastAPI backend server
├── frontend/
│   ├── src/
│   │   ├── App.jsx     # Main React component
│   │   ├── App.css     # Chatbot styles
│   │   ├── main.jsx    # React entry point
│   │   └── index.css   # Global styles
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── poc_agno.py         # Original Agno agent script
└── README.md
```

## Prerequisites

1. **Python 3.10+** with `uv` package manager
2. **Node.js 18+** and npm
3. **Docker** (for Qdrant)
4. **OpenAI API Key**

## Setup Instructions

### 1. Start Qdrant (Vector Database)

```bash
docker run -d --name agno-qdrant -p 6333:6333 qdrant/qdrant
```

### 2. Install Backend Dependencies

```bash
uv sync
```

### 3. Install Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

### 4. Configure API Key

The OpenAI API key is hardcoded in `backend/api.py`. You can also set it in a `.env` file:

```bash
echo "OPENAI_API_KEY=your-key-here" > .env
```

## Running the Application

### Terminal 1: Start Backend Server

```bash
cd backend
uvicorn api:app --reload --port 8000
```

The backend will be available at `http://localhost:8000`

### Terminal 2: Start Frontend

```bash
cd frontend
npm run dev
```

The frontend will be available at `http://localhost:3000`

## API Endpoints

### Health Check
```
GET /health
```

### Chat
```
POST /chat
Body: { "message": "Your question here" }
Response: { "response": "Agent response", "success": true }
```

## Features

- 🤖 **Agno AI Agent** - Powered by OpenAI with knowledge base
- 💬 **Real-time Chat** - Interactive chatbot interface
- 🎨 **Modern UI** - Beautiful gradient design with smooth animations
- 📱 **Responsive** - Works on desktop and mobile
- 🔍 **Knowledge Base** - Answers questions based on crawled website content

## Development

### Backend Development

The backend uses FastAPI with hot-reload enabled. Changes to `backend/api.py` will automatically reload.

### Frontend Development

The frontend uses Vite for fast development. Changes to React components will hot-reload.

### Environment Variables

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=your-key-here
```

## Troubleshooting

1. **Qdrant not running**: Make sure Docker is running and Qdrant container is up
   ```bash
   docker ps | grep qdrant
   ```

2. **Backend errors**: Check that all Python dependencies are installed
   ```bash
   uv sync
   ```

3. **Frontend not connecting**: Verify the API URL in `frontend/src/App.jsx` matches your backend port

4. **CORS errors**: Ensure the backend CORS settings include your frontend URL

## License

MIT

