from dotenv import load_dotenv, find_dotenv
from environs import Env

load_dotenv(find_dotenv(usecwd=True))
env = Env()
