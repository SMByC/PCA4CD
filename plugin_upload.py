#!/usr/bin/env python
"""This script uploads a plugin package to the plugin repository.
Authors: A. Pasotti, V. Picavet
git sha              : $TemplateVCSFormat
"""

import getpass
import sys
import xmlrpc.client
from optparse import OptionParser

# Configuration
PROTOCOL = "https"
SERVER = "plugins.qgis.org"
PORT = "443"
ENDPOINT = "/plugins/RPC2/"
VERBOSE = False


def main(parameters, arguments):
    """Main entry point.

    :param parameters: Command line parameters.
    :param arguments: Command line arguments.
    """
    address = (
        f"{PROTOCOL}://{parameters.username}:{parameters.password}@{parameters.server}:{parameters.port}{ENDPOINT}"
    )
    print(f"Connecting to: {hide_password(address)}")

    server = xmlrpc.client.ServerProxy(address, verbose=VERBOSE)

    try:
        with open(arguments[0], "rb") as handle:
            plugin_id, version_id = server.plugin.upload(xmlrpc.client.Binary(handle.read()))
        print(f"Plugin ID: {plugin_id}")
        print(f"Version ID: {version_id}")
    except xmlrpc.client.ProtocolError as err:
        print("A protocol error occurred")
        print(f"URL: {hide_password(err.url, 0)}")
        print(f"HTTP/HTTPS headers: {err.headers}")
        print(f"Error code: {err.errcode:d}")
        print(f"Error message: {err.errmsg}")
    except xmlrpc.client.Fault as err:
        print("A fault occurred")
        print(f"Fault code: {err.faultCode:d}")
        print(f"Fault string: {err.faultString}")


def hide_password(url, start=6):
    """Returns the http url with password part replaced with '*'.

    :param url: URL to upload the plugin to.
    :type url: str

    :param start: Position of start of password.
    :type start: int
    """
    start_position = url.find(":", start) + 1
    end_position = url.find("@")
    return "{}{}{}".format(url[:start_position], "*" * (end_position - start_position), url[end_position:])


if __name__ == "__main__":
    parser = OptionParser(usage="%prog [options] plugin.zip")
    parser.add_option("-w", "--password", dest="password", help="Password for plugin site", metavar="******")
    parser.add_option("-u", "--username", dest="username", help="Username of plugin site", metavar="user")
    parser.add_option("-p", "--port", dest="port", help="Server port to connect to", metavar="80")
    parser.add_option("-s", "--server", dest="server", help="Specify server name", metavar="plugins.qgis.org")
    options, args = parser.parse_args()
    if len(args) != 1:
        print("Please specify zip file.\n")
        parser.print_help()
        sys.exit(1)
    if not options.server:
        options.server = SERVER
    if not options.port:
        options.port = PORT
    if not options.username:
        # interactive mode
        username = getpass.getuser()
        print(f"Please enter user name [{username}] :", end=" ")

        res = input()
        if res != "":
            options.username = res
        else:
            options.username = username
    if not options.password:
        # interactive mode
        options.password = getpass.getpass()
    main(options, args)
