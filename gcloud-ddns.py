#!/usr/bin/python

import time
import sys
import json
import os
# noinspection PyPackageRequirements
from google.cloud import dns
from requests import get
from googleapiclient import discovery


def main():

    # For this example, the API key is provided as a command-line argument.
    if len(sys.argv) > 1:
        api_key = sys.argv[1]
    else:
        api_key = 'ddns-api-key.json'

    # set OS environ for google authentication
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = api_key
    # json config file for your Google Cloud DNS settings
    config_file = 'cunningtek.json'
    # The ttl of the record we will update. Since this is a dynamic entry, we'll use a short ttl of 60 seconds
    # this will hold the value of our current public IP. Initialised as ''
    # We will only query the Google DNS API to first fetch the record for our host as per the config file
    # and, only when our current IP doesn't match our Google Cloud DNS entry
    # open and read the configuration JSON file
    try:
        with open(config_file, 'r') as f:
            config_dict = json.load(f)
            project = config_dict['project_id']
            managed_zone = config_dict['managed_zone']
            domain = config_dict['domain']
            host = config_dict['host']
            ttl = config_dict['ttl']

    except FileNotFoundError:
        print(f"Configuration file error. Expected {config_file}")

    # http get request to fetch our public IP address from ipify.org
    response = get('https://api.ipify.org?format=json')

    if response.status_code != 200:
        raise Exception(f"ERROR: API request unsuccessful. Expected HTTP 200, got {response.status_code}")

    ip = response.json()["ip"]

    # build the record set which we will submit
    record_set = {'name': host, 'type': 'A', 'ttl': ttl, 'rrdatas': [ip, ]}

    # query the DNS API to check if we have a record set matching our host
    service = discovery.build('dns', 'v1')
    request = service.resourceRecordSets().list(project=project, managedZone=managed_zone, name=host)

    # Use Google's dns.Client to create client object and zone object
    # Note: Here we must provide our Service Account private key
    client = dns.Client(project=project)
    zone = client.zone(managed_zone, domain)

    response = request.execute()  # API call
    print(response)
    # ensure that we got a valid response
    if response is not None and 'rrsets' in response:
        rrset = response['rrsets'][0]
        google_ip = rrset['rrdatas'][0]
        google_host = rrset['name']
        print(f"h: {host} ip: {ip} gh: {rrset['name']} gip: {google_ip}")

        # ensure that the record we received has the same name as the record we want to create
        # if they do not match, then break from this conditional as we do not want to delete the record
        if google_host == host:
            print("Config file host and google host record match")

            if google_ip == ip:
                print("IP and Host information match. Nothing to do here")
                exit(0)
            else:
                # host record exists, but IPs are different. We need to update the record in the cloud
                # to do this, we must first delete the current record, then create a new record
                delete_entry(zone, record_set)
                print(f"Deleting record {record_set}")
                create_entry(zone, record_set)
                print(f"Creating record {record_set}")

        else:
            # for whatever reason, the record returned from google doesn't match the host
            # we have configured in our config file. Exit and log
            print("ERROR: Configured hostname doesn't match hostname returned from google. Exiting")
            exit(1)

    else:
        # response is None so we will create a DNS entry based on our config file
        print(f"No record found. Creating a new record: {record_set}")
        create_entry(zone, record_set)


def create_entry(zone, rs):

    # build the record set
    record_set = zone.resource_record_set(rs['name'], rs['type'], rs['ttl'], rs['rrdatas'])
    # update the IP of our A record

    if zone.exists():
        add_change = zone.changes()
        add_change.add_record_set(record_set)
        add_change.create()  # API request

        while add_change.status != 'done':
            print('Waiting for add record changes to complete')
            time.sleep(30)  # or whatever interval is appropriate
            add_change.reload()  # API request
            print(f"Create Status: {add_change.status}")


def delete_entry(zone, rs):
    # delete the record before we add the new one
    del_change = zone.changes()
    print(f"Deleting {rs['name'], rs['type'], rs['ttl'], rs['rrdatas']}")
    # build the record set to be deleted from rrset
    old_record_set = zone.resource_record_set(rs['name'], rs['type'], rs['ttl'], rs['rrdatas'])
    del_change.delete_record_set(old_record_set)
    del_change.create()  # API request

    # get and print status
    while del_change.status != 'done':
        print('Waiting for changes to complete')
        time.sleep(10)  # or whatever interval is appropriate
        del_change.reload()  # API request
        print(f"Delete Status: {del_change.status}")


if __name__ == '__main__':
    main()
