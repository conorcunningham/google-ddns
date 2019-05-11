import time
import sys
import json
import os
from google.cloud import dns, exceptions as cloudexc
from google.auth import exceptions as authexc
from google.api_core import exceptions as corexc
from requests import get
from googleapiclient import discovery, errors


def main():

    # You can provide the API key as the first parameter
    if len(sys.argv) == 2:
        api_key = sys.argv[1]
    elif len(sys.argv) > 2:
        print("Usage: python gcloud-ddns.py [path_to_api_credentials.json]")
        return 1
    else:
        api_key = "ddns-api-key.json"

    # ensure that the provided credential file exists
    if not os.path.isfile(api_key):
        print("Credential file not found. By default this program checks for ddns-api-key.json in this directory.")
        print("You can specify the path to the credentials as an argument to this script. ")
        print("Usage: python gcloud-ddns.py [path_to_api_credentials.json]")
        return 1

    # set OS environ for google authentication
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = api_key
    # json config file for your Google Cloud DNS settings
    config_file = "ddns-conf.json"

    # read config file settings
    try:
        with open(config_file, "r") as f:
            config_dict = json.load(f)

            project = config_dict["project_id"]
            managed_zone = config_dict["managed_zone"]
            domain = config_dict["domain"]
            host = config_dict["host"]
            ttl = config_dict["ttl"]
            interval = config_dict['interval']

    except FileNotFoundError:
        print(f"Configuration file error. Expected {config_file} present in same directory as this script")
        return 1
    except KeyError as e:
        print(f"The word {e} appears to be misspelt in the configuration file")
        return 1

    # confirm that the last character of host is a '.'. This is a google requirement
    if host[-1] != '.':
        print(f"The host entry in the configuration file must end with a '.', e.g. www.example.com. ")
        return 1

    # query the DNS API to check if we have a record set matching our host
    service = discovery.build("dns", "v1")
    request = service.resourceRecordSets().list(
        project=project, managedZone=managed_zone, name=host
    )

    # Use Google's dns.Client to create client object and zone object
    # Note: Client() will pull the credentials from the on.environ from above
    try:
        client = dns.Client(project=project)
    except authexc.DefaultCredentialsError:
        print("Provided credentials failed. Please ensure you have correct credentials.")
        return 1
    except authexc.GoogleAuthError:
        print("Provided credentials failed. Please ensure you have correct credentials.")
        return 1

    zone = client.zone(managed_zone, domain)

    # this is the program's main loop. Exit with ctl-c
    while True:
        try:
            # http get request to fetch our public IP address from ipify.org
            response = get("https://api.ipify.org?format=json")

            # check that we got a valid response. If not, sleep for interval and go to the top of the loop
            if response.status_code != 200:
                print(f"ERROR: API request unsuccessful. Expected HTTP 200, got {response.status_code}")
                time.sleep(interval)
                # no point going further if we didn't get a valid response,
                # but we also want to try again later, show there be a temporary server issue with ipify.org
                continue

            # this is our public IP address.
            ip = response.json()["ip"]
            # build the record set which we will submit
            record_set = {"name": host, "type": "A", "ttl": ttl, "rrdatas": [ip, ]}

            try:
                response = request.execute()  # API call
            except errors.HttpError as e:
                print(f"Access forbidden. You most likely have a configuration error. Full error: {e}")
                return 1
            except corexc.Forbidden as e:
                print(f"Access forbidden. You most likely have a configuration error. Full error: {e}")
                return 1

            # ensure that we got a valid response
            if response is not None and len(response['rrsets']) > 0:
                rrset = response['rrsets'][0]
                google_ip = rrset['rrdatas']
                google_host = rrset['name']
                google_ttl = rrset['ttl']
                google_type = rrset['type']
                print(f"h: {host} ip: {ip} gh: {rrset['name']} gip: {google_ip}")

                # ensure that the record we received has the same name as the record we want to create
                if google_host == host:
                    print("Config file host and google host record match")

                    if google_ip == ip:
                        print("IP and Host information match. Nothing to do here")
                    else:
                        # host record exists, but IPs are different. We need to update the record in the cloud
                        # to do this, we must first delete the current record, then create a new record

                        del_record_set = {"name": host,
                                          "type": google_type,
                                          "ttl": google_ttl,
                                          "rrdatas": [google_ip, ]
                                          }

                        print(f"Deleting record {del_record_set}")
                        dns_change(zone, del_record_set, 'delete')

                        print(f"Creating record {record_set}")
                        dns_change(zone, record_set, 'create')

                else:
                    # for whatever reason, the record returned from google doesn't match the host
                    # we have configured in our config file. Exit and log
                    print(
                        "ERROR: Configured hostname doesn't match hostname returned from google. No actions taken"
                    )
            else:
                # response is None so we will create a DNS entry based on our config file
                print(f"No record found. Creating a new record: {record_set}")
                dns_change(zone, record_set, 'create')

            # sleep for ten minutes (600 seconds)
            time.sleep(interval)

        # listen for ctl-c and exit if received
        except KeyboardInterrupt:
            print("\nCtl-c received. Goodbye!")
            break
    return 0


def dns_change(zone, rs, cmd):
    # delete the record before we add the new one
    change = zone.changes()
    # build the record set to be deleted from rrset
    record_set = zone.resource_record_set(
        rs["name"], rs["type"], rs["ttl"], rs["rrdatas"]
    )
    if cmd == 'delete':
        change.delete_record_set(record_set)
        print("Deleting!!!!")
    elif cmd == 'create':
        change.add_record_set(record_set)
        print("creating!!!")
    else:
        return

    try:
        change.create()  # API request
    except corexc.FailedPrecondition as e:
        print(f"A precondition for the change failed. Most likely an error in your configuration file. Error: {e}")
    except cloudexc.exceptions as e:
        print(f"A cloudy error occurred. Error: {e}")

    # get and print status
    while change.status != "done":
        print(f"Waiting for {cmd} changes to complete")
        time.sleep(10)  # or whatever interval is appropriate
        change.reload()  # API request
        print(f"{cmd.title()} Status: {change.status}")


if __name__ == "__main__":
    main()
