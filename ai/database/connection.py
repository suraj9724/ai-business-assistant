
import os

import psycopg
from dotenv import load_dotenv

# Load the environment configuration.
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def get_db_connection():
    """Open a connection to the configured PostgreSQL database."""

    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured.")

    # The caller is responsible for closing the connection.
    return psycopg.connect(DATABASE_URL)
