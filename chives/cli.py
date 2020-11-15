import argparse 

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
parser_start_engine.add_argument("security_symbol", 
    help="The symbol of the security that this matching engine operates on")
parser_start_engine.add_argument("-q", "--queue-host", 
    help="hostname of the RabbitMQ server; defaults to localhost",
    dest="queue_host",
    default="localhost")
parser_start_engine.add_argument("-s", "--sql-uri",
    help="Database URI; defaults to sqlite:////tmp/sqlite.db",
    dest="sql_uri",
    default="sqlite:////tmp/sqlite.db")

# Create the parser for initdb command
parser_initdb = subparsers.add_parser('initdb', 
    help="Initialize the database")
parser_initdb.add_argument("-d", "--database",
    help="Database URI; defaults to sqlite:////tmp/sqlite.db",
    dest="sql_uri",
    default="sqlite:////tmp/sqlite.db")
