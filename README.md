
````markdown
# 🚄 KPA Forms - Wheel Specifications API

This is a full-stack containerized application built with **FastAPI** and **PostgreSQL**, designed to manage wheel specification forms.

---

## 🐳 Run Entire App in Docker — No GitHub Clone Required!

You just need **Docker installed** — everything else (code + backend + database) is packaged inside two Docker images available on Docker Hub.

---

## 📦 Docker Images

| Component    | Docker Image                    |
|--------------|----------------------------------|
| FastAPI App  | `maachi/kpa-fastapi:latest`      |
| PostgreSQL   | `maachi/kpa-postgres:latest`     |

---

## 🛠️ Prerequisites

- Install Docker:
```bash
# Linux (Ubuntu/Debian)
sudo apt update && sudo apt install docker.io -y

# macOS (with Homebrew)
brew install docker

# Windows: Install Docker Desktop
````

* Install Docker Compose (if not already):

```bash
sudo apt install docker-compose -y
```

---



You **don’t** need to clone anything from GitHub. All the app and database setup is already inside the images.

---

## 🔐 Environment Variables (`.env`)

Before running, create a `.env` file (in the same directory as your `docker-compose.yml`) with:

```env
POSTGRES_USER=username
POSTGRES_PASSWORD=yourpassword
POSTGRES_DB=yourdbname
```

You can change the values as needed.

---

## 🚀 Steps to Run

1. **Pull the Docker images**:

```bash
docker pull maachi/kpa-fastapi:latest
docker pull maachi/kpa-postgres:latest
```

2. **Start the application**:

```bash
docker-compose up
```

3. **App will be live at**:
   📍 [http://localhost:8000](http://localhost:8000)
   📍 You can test with Postman or open the [index.html](./index.html) if served via a web server.

---

## ✅ API Endpoints

* `GET /` - Health check
* `POST /api/forms/wheel-specifications` - Submit a form
* `GET /api/forms/wheel-specifications` - Get all submissions
* `GET /api/forms/wheel-specifications/{form_number}` - Get one submission
* `PUT /api/forms/wheel-specifications/{form_number}` - Update a form

---

## 🐞 Troubleshooting

* **Can't connect to DB?**

  * Make sure `.env` values match your Docker Compose setup.
  * Check `docker-compose logs` for errors.

* **Port already in use?**

  * Edit `docker-compose.yml` and change the exposed port (`8000`).

---

## 🙌 Credits

Created by [Maachi](https://github.com/maachi)
Docker images: [maachi/kpa-fastapi](https://hub.docker.com/r/maachi/kpa-fastapi),
 [maachi/kpa-postgres](https://hub.docker.com/r/maachi/kpa-postgres)

---

```

---

Let me know if:
- You want to include instructions for serving the `index.html`
- You want to mount volumes for persistent PostgreSQL data
- You plan to auto-build from GitHub on Docker Hub (CI)

I'll help you tailor this README for that.
```
