import importlib

client = importlib.import_module("redis")
driver = __import__("psycopg")
