# any configuration should be stored here
from dotenv import load_dotenv, find_dotenv
from environs import Env

load_dotenv(find_dotenv(usecwd=True))
env = Env()

TOKEN = env.str("TOKEN")
APPNAME = env.str("APPNAME")

