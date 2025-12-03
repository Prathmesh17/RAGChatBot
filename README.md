# RAG Chatbot 🤖

A smart chatbot that answers questions based on your documents using AI embeddings and conversation history.

## 🎥 Demo

https://github.com/user-attachments/assets/5cfb9ace-ab00-471e-b079-72d6476642b1

## ✨ Features

- 📄 Ask questions about your documents
- 💬 Remembers conversation history
- 🚀 FastAPI backend + iOS Frontend App
- 🎯 Smart document retrieval

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Setup API Key
Create `.env` file:
```bash
OPENAI_API_KEY=your-key-here
```

### 3. Run the Chatbot
```bash
python api.py
```

## 📁 Project Structure

```
├── RAGFrontend/           # iOS App
├── docs/                  # Your documents (.txt files)
├── db/                    # Vector database (auto-created)
├── rag_chatbot.py         # Main chatbot
├── api.py                 # API server
└── requirements.txt       # Dependencies
```

## 🔧 Usage

### Interactive Chat
```bash
python rag_chatbot.py
```

### Run API Server
```bash
uvicorn fastapi_example:app --reload
```
Then visit: http://localhost:8000/docs

## 🎯 How It Works

1. **Upload Documents** → Place `.txt` files in `docs/` folder
2. **AI Processes** → Creates searchable embeddings
3. **Ask Questions** → Chatbot finds relevant info
4. **Get Answers** → Context-aware responses with history

## 🎉 That's It!

Your RAG chatbot is ready. Add your documents, run the chatbot, and start asking questions!

---

Made with ❤️ using LangChain, ChromaDB, and OpenAI
