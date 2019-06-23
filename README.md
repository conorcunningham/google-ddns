# CS50 Final Project
**N.B** This project requires the use of Google Cloud, and Google Cloud requires authentication. Specifically, in this project, and when using Google Cloud's DNS, one requires an API key. It is effectively free to use Google DNS for testing, but an account nonetheless is required.

I wrote this to solve an issue that I had at home, and it ended up saving me $100 USD a year. Thank you, Python! Thank you CS50! 

I have opened sourced this project for all to use.

Furthermore, this is deliberately a one file application. It is designed to be easy to clone and use, hence the open source, and it is designed to be used with a Linux service so that it can run in the background. It can theoretically be run on all platforms, MAC, Windows, Linux, embedded linux devices and home network equipment.

I have tested this on Windows 10, Debian 9 Stretch and Max OSX Mojave.

I've had a hoot taking CS50 Web and am currently working on my final project for CS50 Web.

Cheers,

Conor

# Google Cloud Dynamic DNS Client
This is a simple dynamic DNS script for Google Cloud DNS. The script will check for its public IP address, and then based on its configuration it read from the configuration file, check whether Google Cloud DNS has a corresponding DNS entry. If no corresponding entry is found, the script will create one. If a corresponding entry is found, but has an IP address which doesn't match that of what the script found, then the script will update then Google Cloud entry (read delete, then create). Finally, if the scripts configuration file matches that of the Google Cloud DNS entry, then it will sleep for an interval of x, and the process repeats.

This project consists of the following components:

- **gcloud-ddns.py**: the dynamic dns client script
- **ddns-conf.yaml**: programs configuration file
- **requirements.txt**: requirements to be installed
## Requirements
This script requires **Python 3.6 or greater**. f-strings are extensively used. Package requirements are listed in [requirements.txt](requirements.txt)
## Usage
```bash
Usage: python gcloud-ddns.py [path_to_configuration_file.yaml]
```
## Setup
```bash
$ git clone git@github.com:conorcunningham/google-ddns.git
$ cd google-ddns
$ python3 gcloud-ddns.py
```
The script will run in the foreground. I'm going to play around with it and test it to see if it can run reliably as a service.
## Configuration file
The configuration for the script is read from a yaml file. Here are the contents of the example [ddns-conf.yaml](ddns-config.yaml) file
``` yaml
api-key: './ddns-api-key.json'
logfile: './ddns.log'
hosts:
    -   host: 'firewall.example.com.'
        project_id: 'fluffy-penguin-242411'
        managed_zone: 'example'
        domain: 'example.com'
        ttl: 60
        interval: 600

    -   host: 'www.example-two.com.'
        project_id: 'fluffy-penguin-242411'
        managed_zone: 'example-two'
        domain: 'example-two.com'
        ttl: 60
        interval: 600

```
The script accepts one optional CLI argument which is the path to the configuration file. If none is given, the script will look for ```ddns-config.yaml``` in the same directory as the script.


- **host**: the fully-qualified domain name of the host you want to set. *_NB_** You must include the . after the .com. This is a Google requirement/
- **project_id**: Your project ID within Google Cloud
- **managed_zone**: The name of your managed zone in Google Cloud
- **domain**: Your domain name
- **ttl**: The number of seconds for the TTL
- **interval**: How long the script will sleep before running again
- **api-key**: Path to the API key in JSON format
- **log-path**: Path to the logfile

## Authentication 
In order to use the Google Cloud API, you will need an API key for your account. This key will be a json file and must be configured in the configuration file.

The script will set ```GOOGLE_APPLICATION_CREDENTIALS``` environmental variable to the path of your API key and Google's modules will use this environmental variable to handle authentication.

```python        
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = api_key
```
## ipify.org API
This project makes use of the snazzy [ipify.org](https://www.ipify.org) API for fetching the clients public IP address.

