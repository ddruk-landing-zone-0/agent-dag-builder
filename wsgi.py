from app import app as application
import os

app = application

if __name__ == "__main__":
    application.run(host='0.0.0.0', port=8080)
    