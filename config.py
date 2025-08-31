import os
from dotenv import load_dotenv

load_dotenv()  # loads .env file automatically

BOT_TOKEN = os.getenv("BOT_TOKEN", "8447850903:AAFWZcZwT47xlvC8KuNDFCOmKCRj_F6F76U"),
