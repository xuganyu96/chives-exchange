import argparse 
from chives.db import SQLALCHEMY_URI, DEFAULT_SQLALCHEMY_URI

parser = argparse.ArgumentParser(prog="chives")
subparsers = parser.add_subparsers(help="subcommand help", required=True,
# TODO: https://stackoverflow.com/questions/18282403/argparse-with-required-subcommands/18283730
                                    dest='subcommand')
# Arguments that are shared
parser.add_argument("-v", "--verbose",
    help="If used, will provide more detailed output",
    action="store_true")

# Create the parser for the start_engine command
parser_start_engine = subparsers.add_parser('start_engine', 
    help="Start an instance of a matching engine")
parser_start_engine.add_argument("-q", "--queue-host", 
    help="hostname of the RabbitMQ server; defaults to localhost",
    dest="queue_host",
    default="localhost")
parser_start_engine.add_argument("-s", "--sql-uri",
    help=f"Database URI; defaults to {DEFAULT_SQLALCHEMY_URI}",
    dest="sql_uri",
    default=f"{DEFAULT_SQLALCHEMY_URI}")
parser_start_engine.add_argument("--dry-run",
    help="Do not heartbeat the matching engine when a message is received",
    dest="dry_run",
    action="store_true",
    default=False)

# Create the parser for initdb command
parser_initdb = subparsers.add_parser('initdb', 
    help="Initialize the database")
parser_initdb.add_argument("-s", "--sql-uri",
    help=f"Database URI; defaults to {DEFAULT_SQLALCHEMY_URI}",
    dest="sql_uri",
    default=f"{DEFAULT_SQLALCHEMY_URI}")

# Create the parser for webserver command
parser_webserver = subparsers.add_parser('webserver', 
    help="Initialize the database")
parser_webserver.add_argument("-p", "--port",
    help="Flask application port, defaults to 5000",
    dest="webserver_port",
    default="5000")
parser_webserver.add_argument("-d", "--debug",
    help="If used, will make the Flask app run in debug mode",
    dest="debug",
    action="store_true")
parser_webserver.add_argument("-s", "--sql-uri",
    help=f"Database URI; defaults to {DEFAULT_SQLALCHEMY_URI}",
    dest="sql_uri", 
    default=DEFAULT_SQLALCHEMY_URI)
