import os

# Keep this in sync with docker-compose.yml's port mapping and .env's
# SERVER_PORT -- changing one without the other leaves the backend
# listening on a port nothing points at.
SERVER_PORT = int(os.environ.get("SERVER_PORT", 8000))
