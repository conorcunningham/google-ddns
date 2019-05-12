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
import json
import os
import logging
from google.cloud import dns, exceptions as cloudexc
from google.auth import exceptions as authexc
from google.api_core import exceptions as corexc
from googleapiclient import discovery, errors
from requests import get


def main():

    # You can provide the config file as the first parameter
    if len(sys.argv) == 2:
        config_file = sys.argv[1]
    elif len(sys.argv) > 2:
        print("Usage: python gcloud-ddns.py [path_to_config_file.json]")
        return 1
    else:
        config_file = "ddns-config.json"

    # read config file settings
    try:
        with open(config_file, "r") as f:
            config_dict = json.load(f)
            project = config_dict["project_id"]
            managed_zone = config_dict["managed_zone"]
            domain = config_dict["domain"]
            host = config_dict["host"]
            ttl = config_dict["ttl"]
            interval = config_dict["interval"]
            api_key = config_dict["api-key"]
            logfile = config_dict["log-path"]

    except FileNotFoundError:
        print(
            f"Configuration file error. Expected {config_file} present in same directory as this script"
        )
        return 1
    except KeyError as e:
        print(
            f"There is a configuration error. Check to see if the word {e} is misspelt,"
            f" or in fact exists in the configuration file."
        )
        return 1

    # confirm that the last character of host is a '.'. This is a google requirement
    if host[-1] != ".":
        print(
            f"The host entry in the configuration file must end with a '.', e.g. www.example.com. "
        )
        return 1

    # ensure that the provided credential file exists
    if not os.path.isfile(api_key):
        print(
            "Credential file not found. By default this program checks for ddns-api-key.json in this directory."
        )
        print(
            "You can specify the path to the credentials as an argument to this script. "
        )
        print("Usage: python gcloud-ddns.py [path_to_config_file.json]")
        return 1

    logging.basicConfig(
        level=logging.DEBUG,
        filename=logfile,
        filemode="w",
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    # set OS environ for google authentication
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = api_key

    # setup our objects that will be used to query the Google API
    # N.B. cache_discover if false. This prevents google module exceptions
    # This is not a performance critical script, so shouldn't be a problem.
    service = discovery.build("dns", "v1", cache_discovery=False)
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

    # this is the program's main loop. Exit with ctl-c
    while True:
        try:
            # http get request to fetch our public IP address from ipify.org
            response = get("https://api.ipify.org?format=json")

            # check that we got a valid response. If not, sleep for interval and go to the top of the loop
            if response.status_code != 200:
                logging.error(
                    f"API request unsuccessful. Expected HTTP 200, got {response.status_code}"
                )
                time.sleep(interval)
                # no point going further if we didn't get a valid response,
                # but we also want to try again later, should there be a temporary server issue with ipify.org
                continue

            # this is our public IP address.
            ip = response.json()["ip"]
            # build the record set based on our configuration file
            record_set = {"name": host, "type": "A", "ttl": ttl, "rrdatas": [ip]}

            # attempt to get the DNS information of our host from Google
            try:
                response = request.execute()  # API call
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
            if response is not None and len(response["rrsets"]) > 0:
                rrset = response["rrsets"][0]
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
                            f"IP and Host information match. Nothing to do here. Going to sleep for {interval} seconds"
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

            time.sleep(interval)

        except KeyboardInterrupt:
            print("\nCtl-c received. Goodbye!")
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
