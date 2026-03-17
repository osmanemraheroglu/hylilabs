<div align="center">

<img src="public/images/Logo_600x400.png" alt="HyliLabs Logo" width="200"/>

# HyliLabs

**AI-Powered HR Recruitment Platform**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-3776ab.svg)](https://python.org)
[![React](https://img.shields.io/badge/React-18+-61dafb.svg)](https://reactjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg)](https://fastapi.tiangolo.com)

[Demo](https://hylilabs.com) • [Documentation](#-documentation) • [Contributing](CONTRIBUTING.md)

</div>

---

## 🚀 Overview

HyliLabs is an enterprise-grade AI-powered recruitment platform designed for the Turkish market. It combines multiple AI models (Claude, Gemini, OpenAI, Nous Research) for intelligent CV analysis, candidate matching, and hiring decisions.

### Key Features

- **🤖 Multi-AI Scoring System** - Consensus-based evaluation using 4 AI models
- **📄 Intelligent CV Parsing** - Automatic extraction of skills, experience, and education
- **🎯 Smart Matching** - 100-point scoring system with weighted categories
- **🏗️ Industry Intelligence** - Specialized support for construction sector
- **📅 Interview Management** - Scheduling, reminders, and KVKK-compliant confirmations
- **🔒 KVKK Compliance** - Full Turkish data protection law compliance
- **🏢 Multi-tenant Architecture** - Company-level data isolation

---

## 🛠️ Tech Stack

### Backend
- **Framework:** FastAPI (Python 3.11+)
- **Database:** SQLite with WAL mode
- **AI Models:** Claude (Anthropic), Gemini (Google), GPT (OpenAI), Hermes (Nous Research)
- **Authentication:** JWT with role-based access control

### Frontend
- **Framework:** React 18 + TypeScript
- **UI Library:** shadcn/ui + Tailwind CSS
- **Routing:** TanStack Router
- **Build Tool:** Vite

### Infrastructure
- **Deployment:** PM2 + Nginx
- **SSL:** Let's Encrypt (Certbot)
- **Server:** Ubuntu 22.04 LTS

---

## 📦 Installation

### Prerequisites

- Python 3.11+
- Node.js 18+
- pnpm or npm

### Quick Start

1. **Clone the repository**
```bash
git clone https://github.com/osmanemraheroglu/hylilabs.git
cd hylilabs
```

2. **Backend Setup**
```bash
cd api
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
```

3. **Frontend Setup**
```bash
cd ..  # Back to root
pnpm install
cp .env.example .env
# Edit .env with your settings
```

4. **Start Development Servers**
```bash
# Terminal 1 - Backend
cd api && uvicorn main:app --reload --port 8000

# Terminal 2 - Frontend
pnpm dev
```

5. **Access the application**
- Frontend: http://localhost:5173
- API Docs: http://localhost:8000/docs

---

## 🏗️ Architecture

```
hylilabs/
├── api/                    # FastAPI Backend
│   ├── core/              # Core modules (scoring, CV parsing, matching)
│   │   ├── scoring_v2.py  # 100-point scoring system
│   │   ├── scoring_v3/    # AI-based evaluation
│   │   ├── cv_parser.py   # CV parsing with Claude
│   │   └── candidate_matcher.py
│   ├── routes/            # API endpoints
│   ├── database.py        # SQLite operations
│   └── main.py            # FastAPI app
├── src/                   # React Frontend
│   ├── features/          # Feature modules
│   ├── components/        # Shared components
│   └── routes/            # TanStack Router
├── data/                  # Database & CV storage
└── docs/                  # Documentation
```

---

## 📊 Scoring System

HyliLabs uses a hybrid scoring approach:

### V2 Scoring (Deterministic) - 100 Points
| Category | Max Points | Details |
|----------|------------|---------|
| Position Match | 20 | Title (8) + Sector (7) + Seniority (5) |
| Technical Skills | 40 | Must-have (15) + Critical (15) + Important (10) |
| General | 15 | Experience (8) + Education (7) |
| Task Match | 15 | Job description alignment |
| Elimination | 10 | Location (5) + Other (5) |

### V3 Scoring (AI-Based)
- Multi-model consensus (Claude, Gemini, OpenAI, Hermes)
- Final score: `(V3 × 0.60) + (V2 × 0.40)`

---

## 🔒 Security

- **API Keys**: Stored in `.env` files, never committed to repository
- **KVKK Compliance**: Full Turkish data protection law compliance
- **Multi-tenant Isolation**: Company-level data separation
- **JWT Authentication**: Secure token-based authentication
- **Rate Limiting**: API endpoint protection

---

## 🗺️ Roadmap

| Feature | Status |
|---------|--------|
| Multi-AI Scoring System | ✅ Complete |
| CV Intelligence | ✅ Complete |
| Construction Industry Intelligence | ✅ Complete |
| Dashboard Analytics | ✅ Complete |
| Fallback Chain System | ✅ Complete |
| Career Page | 🔜 Coming Soon |
| Public API | 🔜 Coming Soon |
| Mobile App | 🔜 Planned |

---

## 🤝 Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [Nous Research](https://nousresearch.com) for Hermes model
- [Google](https://ai.google.dev) for Gemini API
- [Anthropic](https://anthropic.com) for Claude API
- [OpenAI](https://openai.com) for GPT API

---

<div align="center">

Built with ❤️ by [@osmanemraheroglu](https://github.com/osmanemraheroglu)

**[HyliLabs](https://hylilabs.com)** — Smarter Hiring, Powered by AI

</div>
