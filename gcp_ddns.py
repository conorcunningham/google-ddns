""" A dynamic DNS client Google Cloud DDNS

This script will, based on its configuration file, query the GCloud DNS API.
It will create a Resource Record Set (RRSET)in GCloud if no such record
exists that matches the configuration file. If a match is found, the script
will check its host's current public IP address, and if it is found to be
different than that in GCloud, will first delete the RRSET, then create a
new RRSET.

Every x seconds, as defined by the user with the variable interval, the script
will repeat the process.

"""
import time
import sys
import os
import yaml
import logging
import signal
from google.cloud import dns, exceptions as cloudexc
from google.auth import exceptions as authexc
from google.api_core import exceptions as corexc
from googleapiclient import discovery, errors
import requests

CONFIG_PARAMS = ['project_id', 'managed_zone', 'host', 'ttl', 'interval']


# This makes sure that SIGTERM signal is handled (for example from Docker)
def handle_sigterm(*args):
    raise KeyboardInterrupt()


signal.signal(signal.SIGTERM, handle_sigterm)


# noinspection PyUnboundLocalVariable
def main():

    # initialize console logger
    logging.getLogger().setLevel(logging.DEBUG)
    
    logFormatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    
    consoleHandler = logging.StreamHandler()
    consoleHandler.setFormatter(logFormatter)
    logging.getLogger().addHandler(consoleHandler)


    # You can provide the config file as the first parameter
    if len(sys.argv) == 2:
        config_file = sys.argv[1]
    elif len(sys.argv) > 2:
        logging.error("Usage: python gcp_ddns.py [path_to_config_file.yaml]")
        return 1
    else:
        config_file = "ddns-config.yaml"

    # Read YAML configuration file and set initial parameters for logfile and api key
    with open(config_file, 'r') as stream:
        try:
            config = yaml.safe_load(stream)
            logging.info(config)
            if 'api-key' in config:
                api_key = config['api-key']
            else:
                logging.error(f"api_key must be defined in {config_file}")
                exit(1)

            if 'logfile' in config:
                logfile = config['logfile']
            else:
                logging.error(f"logfile must be defined in {config_file}")
                exit(1)

            # iterate through our required config parameters and each host entry in the config file
            # check that all requisite parameters are included in the file before proceeding.

        except yaml.YAMLError:
            logging.error(f"There was an error loading configuration file: {config_file}")
            exit(1)

    # ensure that the provided credential file exists
    if not os.path.isfile(api_key):
        logging.error(
            "Credential file not found. By default this program checks for ddns-api-key.json in this directory.\n"
            + "You can specify the path to the credentials as an argument to this script. "
            + "Usage: python gcp_ddns.py [path_to_config_file.json]"
        )
        return 1
    
    # initialize file logger
    fileHandler = logging.FileHandler(filename=logfile, mode="w")
    fileHandler.setFormatter(logFormatter)
    logging.getLogger().addHandler(fileHandler)

    # set OS environ for google authentication
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = api_key

    # setup our objects that will be used to query the Google API
    # N.B. cache_discover if false. This prevents google module exceptions
    # This is not a performance critical script, so shouldn't be a problem.
    service = discovery.build("dns", "v1", cache_discovery=False)

    # this is the program's main loop. Exit with ctl-c
    while True:
        try:
            for count, config_host in enumerate(config['hosts'], start=1):
                for key in CONFIG_PARAMS:
                    if key not in config_host:
                        logging.error(f"{key} not found in config file {config_file}. Please ensure it is.")
                        exit(1)

                project = config_host["project_id"]
                managed_zone = config_host["managed_zone"]
                domain = config_host["domain"]
                host = config_host["host"]
                ttl = config_host["ttl"]
                interval = config_host["interval"]

                # confirm that the last character of host is a '.'. This is a google requirement
                if host[-1] != ".":
                    logging.error(
                        f"The host entry in the configuration file must end with a '.', e.g. www.example.com. "
                    )
                    return 1

                # attempt to get IP address early on. This will help us determine
                # if we have an internet connection. If we don't we should catch
                # the exception, sleep and go to the top of the loop
                # http get request to fetch our public IP address from ipify.org
                # if it fails for whatever reason, sleep, and go back to the top of the loop
                try:
                    ipify_response = requests.get("https://api.ipify.org?format=json")
                except requests.exceptions.ConnectionError as exc:
                    logging.error(f"Timed out trying to reach api.ipify.org", exc_info=exc)
                    time.sleep(interval)
                except requests.exceptions.RequestException as exc:
                    logging.error(
                        f"Requests error when trying to fetch current local IP. Exception: {exc}",
                        exc_info=exc
                    )
                    continue

                # check that we got a valid response. If not, sleep for interval and go to the top of the loop
                if ipify_response.status_code != 200:
                    logging.error(
                        f"API request unsuccessful. Expected HTTP 200, got {gcp_record_set.status_code}"
                    )
                    time.sleep(interval)
                    # no point going further if we didn't get a valid response,
                    # but we also want to try again later, should there be a temporary server issue with ipify.org
                    continue

                # this is our public IP address.
                ip = ipify_response.json()["ip"]

                # this is where we build our resource record set and what we will use to call the api
                # further down in the script.
                request = service.resourceRecordSets().list(
                    project=project, managedZone=managed_zone, name=host
                )

                # Use Google's dns.Client to create client object and zone object
                # Note: Client() will pull the credentials from the os.environ from above
                try:
                    client = dns.Client(project=project)
                except authexc.DefaultCredentialsError:
                    logging.error(
                        "Provided credentials failed. Please ensure you have correct credentials."
                    )
                    return 1
                except authexc.GoogleAuthError:
                    logging.error(
                        "Provided credentials failed. Please ensure you have correct credentials."
                    )
                    return 1

                # this is the object which will be sent to Google and queried by us.
                zone = client.zone(managed_zone, domain)

                # build the record set based on our configuration file
                record_set = {"name": host, "type": "A", "ttl": ttl, "rrdatas": [ip]}

                # attempt to get the DNS information of our host from Google
                try:
                    gcp_record_set = request.execute()  # API call
                except errors.HttpError as e:
                    logging.error(
                        f"Access forbidden. You most likely have a configuration error. Full error: {e}"
                    )
                    return 1
                except corexc.Forbidden as e:
                    logging.error(
                        f"Access forbidden. You most likely have a configuration error. Full error: {e}"
                    )
                    return 1

                # ensure that we got a valid response
                if gcp_record_set is not None and len(gcp_record_set["rrsets"]) > 0:
                    rrset = gcp_record_set["rrsets"][0]
                    google_ip = rrset["rrdatas"][0]
                    google_host = rrset["name"]
                    google_ttl = rrset["ttl"]
                    google_type = rrset["type"]
                    logging.debug(
                        f"config_h: {host} current_ip: {ip} g_host: {rrset['name']} g_ip: {google_ip}"
                    )

                    # ensure that the record we received has the same name as the record we want to create
                    if google_host == host:
                        logging.info("Config file host and google host record match")

                        if google_ip == ip:
                            logging.info(
                                f"IP and Host information match. Nothing to do here. "
                            )
                        else:
                            # host record exists, but IPs are different. We need to update the record in the cloud.
                            # To do this, we must first delete the current record, then create a new record

                            del_record_set = {
                                "name": host,
                                "type": google_type,
                                "ttl": google_ttl,
                                "rrdatas": [google_ip],
                            }

                            logging.debug(f"Deleting record {del_record_set}")
                            if not dns_change(zone, del_record_set, "delete"):
                                logging.error(
                                    f"Failed to delete record set {del_record_set}"
                                )

                            logging.debug(f"Creating record {record_set}")
                            if not dns_change(zone, record_set, "create"):
                                logging.error(f"Failed to create record set {record_set}")

                    else:
                        # for whatever reason, the record returned from google doesn't match the host
                        # we have configured in our config file. Exit and log
                        logging.error(
                            "Configured hostname doesn't match hostname returned from google. No actions taken"
                        )
                else:
                    # response to our request returned no results, so we'll create a DNS record
                    logging.info(f"No record found. Creating a new record: {record_set}")
                    if not dns_change(zone, record_set, "create"):
                        logging.error(f"Failed to create record set {record_set}")

                # only go to sleep if we have cycled through all hosts
                if count == len(config['hosts']):
                    logging.info(
                        f"Going to sleep for {interval} seconds "
                    )
                    time.sleep(interval)

        except KeyboardInterrupt:
            logging.error("\nCtl-c received. Goodbye!")
            break
    return 0


def dns_change(zone, rs, cmd):
    """ Function to create or delete a DNS record

    :param zone: google.cloud.dns.zone.ManagedZone'
            The zone which we are configuring in Google Cloud DNS
    :param rs:  dict
            Contains all the elements we need to create the record set to be submitted to the API
    :param cmd: str
            Either 'create' or 'delete'. This decides which action to take towards Google Cloud
    :return: bool
            True if we succeeded in a creation or deletion of a record set, otherwise False
    """

    change = zone.changes()
    # build the record set to be deleted or created
    record_set = zone.resource_record_set(
        rs["name"], rs["type"], rs["ttl"], rs["rrdatas"]
    )
    if cmd == "delete":
        change.delete_record_set(record_set)
        logging.debug(f"Deleting record set: {record_set}")
    elif cmd == "create":
        change.add_record_set(record_set)
        logging.debug(f"creating record set : {record_set}")
    else:
        return False

    try:
        change.create()  # API request
    except corexc.FailedPrecondition as e:
        logging.error(
            f"A precondition for the change failed. Most likely an error in your configuration file. Error: {e}"
        )
        return False
    except cloudexc.exceptions as e:
        logging.error(f"A cloudy error occurred. Error: {e}")
        return False

    # get and print status
    while change.status != "done":
        logging.info(f"Waiting for {cmd} changes to complete")
        time.sleep(10)  # or whatever interval is appropriate
        change.reload()  # API request
        logging.info(f"{cmd.title()} Status: {change.status}")

    return True


if __name__ == "__main__":
    main()
