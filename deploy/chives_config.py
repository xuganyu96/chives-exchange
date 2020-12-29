"""First read environment variables, then define a giant Python dictionary that 
contains configuration options. Where options are specified by environment 
variables, use what is specified by environment variables; otherwise, use a 
default value
"""
import os
from chives.db import DEFAULT_SQLALCHEMY_URI

CONFIG = {
    'sql_alchemy_conn': os.getenv('SQL_ALCHEMY_CONN', DEFAULT_SQLALCHEMY_URI),
    'rabbitmq_host': os.getenv("RABBITMQ_HOST", "localhost"),
    'rabbitmq_port': os.getenv("RABBITMQ_PORT", 5672),
    'rabbitmq_vhost': os.getenv("RABBITMQ_VHOST", '/'),
    'rabbitmq_user': os.getenv("RABBITMQ_USER", 'guest'),
    'rabbitmq_password': os.getenv("RABBITMQ_PASSWORD", 'guest')
}